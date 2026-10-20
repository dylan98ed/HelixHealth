"""Build DICOM files while keeping the source image out of persistent storage."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from io import BytesIO
from math import ceil

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from pydicom import dcmread
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.errors import InvalidDicomError
from pydicom.pixels import apply_color_lut, apply_modality_lut, apply_voi_lut
from pydicom.uid import (
    PYDICOM_IMPLEMENTATION_UID,
    UID,
    ExplicitVRLittleEndian,
    SecondaryCaptureImageStorage,
    generate_uid,
)

MAX_UPLOAD_BYTES = 32 * 1024 * 1024
MAX_PIXELS = 24_000_000
PREVIEW_MAX_EDGE = 1600


class ImageProcessingError(ValueError):
    pass


def _year(value: object) -> int | None:
    digits = str(value or "")[:4]
    if len(digits) != 4 or not digits.isdecimal():
        return None
    year = int(digits)
    return year if 1850 <= year <= date.today().year else None


def _sex(value: object) -> str:
    return (
        str(value or "").upper() if str(value or "").upper() in {"M", "F", "O"} else ""
    )


def _file_meta(
    sop_class_uid: str, sop_instance_uid: str, transfer_syntax: str
) -> FileMetaDataset:
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = UID(sop_class_uid)
    meta.MediaStorageSOPInstanceUID = UID(sop_instance_uid)
    meta.TransferSyntaxUID = UID(transfer_syntax)
    meta.ImplementationClassUID = PYDICOM_IMPLEMENTATION_UID
    return meta


def _serialize(dataset: FileDataset) -> bytes:
    buffer = BytesIO()
    dataset.save_as(buffer, enforce_file_format=True)
    return buffer.getvalue()


def _set_demographics(
    dataset: FileDataset, birth_year: int | None, study_year: int | None, sex: str
) -> None:
    dataset.PatientName = ""
    dataset.PatientID = ""
    dataset.PatientBirthDate = f"{birth_year}0101" if birth_year else ""
    dataset.PatientSex = sex
    dataset.StudyDate = f"{study_year}0101" if study_year else ""
    dataset.StudyTime = ""
    dataset.StudyID = ""
    dataset.AccessionNumber = ""
    dataset.ReferringPhysicianName = ""
    dataset.PatientIdentityRemoved = "YES"
    dataset.LongitudinalTemporalInformationModified = "MODIFIED"
    dataset.DeidentificationMethod = "HelixHealth metadata removal; year only"


def convert_raster(
    data: bytes, *, source_format: str, birth_year: int, study_year: int, sex: str
) -> bytes:
    try:
        with Image.open(BytesIO(data)) as source:
            if source.format != source_format:
                raise ImageProcessingError(
                    "The image content does not match its file type."
                )
            if source.width * source.height > MAX_PIXELS:
                raise ImageProcessingError("The image exceeds the 24 megapixel limit.")
            image = ImageOps.exif_transpose(source)
            if image.mode not in {"L", "RGB"}:
                image = image.convert("RGB")
            pixels = image.tobytes()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ImageProcessingError("The JPG or PNG file could not be read.") from error

    sop_instance_uid = generate_uid()
    dataset = FileDataset(
        "",
        {},
        file_meta=_file_meta(
            str(SecondaryCaptureImageStorage),
            sop_instance_uid,
            str(ExplicitVRLittleEndian),
        ),
        preamble=b"\0" * 128,
    )
    dataset.SOPClassUID = SecondaryCaptureImageStorage
    dataset.SOPInstanceUID = sop_instance_uid
    dataset.StudyInstanceUID = generate_uid()
    dataset.SeriesInstanceUID = generate_uid()
    dataset.Modality = "OT"
    dataset.ConversionType = "WSD"
    dataset.Manufacturer = ""
    dataset.ContentDate = ""
    dataset.ContentTime = ""
    dataset.ImageType = ["DERIVED", "SECONDARY"]
    dataset.SeriesNumber = 1
    dataset.InstanceNumber = 1
    dataset.Rows = image.height
    dataset.Columns = image.width
    dataset.SamplesPerPixel = 1 if image.mode == "L" else 3
    dataset.PhotometricInterpretation = "MONOCHROME2" if image.mode == "L" else "RGB"
    if image.mode == "RGB":
        dataset.PlanarConfiguration = 0
    dataset.BitsAllocated = 8
    dataset.BitsStored = 8
    dataset.HighBit = 7
    dataset.PixelRepresentation = 0
    dataset.PixelData = pixels
    dataset.BurnedInAnnotation = "YES"  # Pixels have not been reviewed or cleaned.
    _set_demographics(dataset, birth_year, study_year, sex)
    return _serialize(dataset)


_SAFE_CS = {
    "Modality",
    "ImageType",
    "PhotometricInterpretation",
    "ConversionType",
    "PatientPosition",
    "PatientOrientation",
    "Laterality",
    "ImageLaterality",
    "BodyPartExamined",
    "PresentationLUTShape",
    "RescaleType",
    "LossyImageCompression",
    "BurnedInAnnotation",
    "RecognizableVisualFeatures",
    "PixelIntensityRelationship",
    "UltrasoundColorDataPresent",
    "VolumetricProperties",
    "FrameType",
    "PixelPresentation",
    "VolumeBasedCalculationTechnique",
    "ComplexImageComponent",
    "AcquisitionContrast",
}
_SAFE_TEXT = {"SpecificCharacterSet"}
_FREE_TEXT_VR = {"AE", "AS", "LO", "LT", "PN", "SH", "ST", "UC", "UR", "UT"}
_BINARY_VR = {"OB", "OD", "OF", "OL", "OV", "OW"}
_IMAGE_BINARY = {
    "PixelData",
    "LUTData",
    "RedPaletteColorLookupTableData",
    "GreenPaletteColorLookupTableData",
    "BluePaletteColorLookupTableData",
    "AlphaPaletteColorLookupTableData",
    "SegmentedRedPaletteColorLookupTableData",
    "SegmentedGreenPaletteColorLookupTableData",
    "SegmentedBluePaletteColorLookupTableData",
    "SegmentedAlphaPaletteColorLookupTableData",
}


def _sanitize_dataset(dataset: Dataset, uid_map: dict[str, str]) -> None:
    dataset.remove_private_tags()
    for element in list(dataset):
        tag = element.tag
        if tag.group & 0xFF00 in {0x5000, 0x6000} or tag.group in {0x0070, 0x0042}:
            del dataset[tag]  # Curves, overlays, presentation graphics and documents.
        elif element.VR == "SQ":
            for item in element.value:
                _sanitize_dataset(item, uid_map)
            if not any(item for item in element.value):
                del dataset[tag]
        elif element.VR in {"DA", "DT", "TM"}:
            del dataset[tag]
        elif element.VR == "UI" and element.keyword not in {
            "SOPClassUID",
            "TransferSyntaxUID",
        }:
            old_uid = str(element.value)
            element.value = (
                uid_map.setdefault(old_uid, generate_uid()) if old_uid else ""
            )
        elif element.VR in _FREE_TEXT_VR and element.keyword not in _SAFE_TEXT:
            del dataset[tag]
        elif element.VR == "CS" and element.keyword not in _SAFE_CS:
            del dataset[tag]
        elif element.VR in _BINARY_VR and element.keyword not in _IMAGE_BINARY:
            del dataset[tag]
        elif element.VR == "UN":
            del dataset[tag]


def anonymize_dicom(data: bytes) -> tuple[bytes, int | None, int | None, str]:
    try:
        original = dcmread(BytesIO(data))
    except (InvalidDicomError, OSError, ValueError) as error:
        raise ImageProcessingError("The DICOM file could not be read.") from error
    if (
        "PixelData" not in original
        or not original.get("Rows")
        or not original.get("Columns")
    ):
        raise ImageProcessingError("A DICOM image with pixel data is required.")
    if not original.get("SOPClassUID"):
        raise ImageProcessingError("The DICOM SOP class is missing.")
    try:
        frame_count = int(original.get("NumberOfFrames", 1))
    except (TypeError, ValueError) as error:
        raise ImageProcessingError("The DICOM frame count is invalid.") from error
    if frame_count != 1:
        raise ImageProcessingError("Only single-frame DICOM images are supported.")
    if not getattr(original, "file_meta", None) or not original.file_meta.get(
        "TransferSyntaxUID"
    ):
        raise ImageProcessingError("The DICOM transfer syntax is missing.")

    birth_year = _year(original.get("PatientBirthDate"))
    study_year = _year(original.get("StudyDate")) or _year(
        original.get("AcquisitionDate")
    )
    sex = _sex(original.get("PatientSex"))
    dataset = deepcopy(original)
    uid_map: dict[str, str] = {}
    _sanitize_dataset(dataset, uid_map)
    for keyword in ("StudyInstanceUID", "SeriesInstanceUID", "SOPInstanceUID"):
        if not dataset.get(keyword):
            dataset.__setattr__(keyword, generate_uid())
    dataset.file_meta = _file_meta(
        str(dataset.SOPClassUID),
        str(dataset.SOPInstanceUID),
        str(original.file_meta.TransferSyntaxUID),
    )
    dataset.BurnedInAnnotation = (
        "YES"  # Deliberately never claim that pixels are clean.
    )
    _set_demographics(dataset, birth_year, study_year, sex)
    return _serialize(dataset), birth_year, study_year, sex


def _display_grayscale(pixels: np.ndarray, dataset: Dataset) -> Image.Image:
    values = apply_modality_lut(pixels, dataset)
    values = np.asarray(apply_voi_lut(values, dataset), dtype=np.float64)
    finite = np.isfinite(values)
    if not finite.any():
        raise ImageProcessingError("The DICOM pixels cannot be displayed.")
    minimum = float(values[finite].min())
    maximum = float(values[finite].max())
    values = np.nan_to_num(values, nan=minimum, posinf=maximum, neginf=minimum)
    if maximum > minimum:
        values = (values - minimum) * (255.0 / (maximum - minimum))
    else:
        values = np.zeros_like(values)
    if dataset.PhotometricInterpretation == "MONOCHROME1":
        values = 255.0 - values
    return Image.fromarray(np.clip(values, 0, 255).astype(np.uint8))


def _display_color(pixels: np.ndarray) -> Image.Image:
    values = np.asarray(pixels)
    if values.ndim != 3 or values.shape[2] not in {3, 4}:
        raise ImageProcessingError("The DICOM color pixels cannot be displayed.")
    if values.dtype != np.uint8:
        values = values.astype(np.float64)
        minimum = float(values.min())
        maximum = float(values.max())
        if maximum > minimum:
            values = (values - minimum) * (255.0 / (maximum - minimum))
        else:
            values = np.zeros_like(values)
        values = np.clip(values, 0, 255).astype(np.uint8)
    return Image.fromarray(values)


def render_preview(data: bytes) -> bytes:
    """Render a bounded, browser-friendly preview from the saved DICOM bytes."""
    try:
        dataset = dcmread(BytesIO(data))
        rows = int(dataset.Rows)
        columns = int(dataset.Columns)
        if rows <= 0 or columns <= 0 or rows * columns > MAX_PIXELS:
            raise ImageProcessingError("The DICOM exceeds the 24 megapixel preview limit.")
        interpretation = str(dataset.PhotometricInterpretation)
        pixels = dataset.pixel_array
        stride = max(1, ceil(max(rows, columns) / PREVIEW_MAX_EDGE))
        pixels = pixels[::stride, ::stride]
        if interpretation in {"MONOCHROME1", "MONOCHROME2"}:
            image = _display_grayscale(pixels, dataset)
        elif interpretation == "PALETTE COLOR":
            image = _display_color(apply_color_lut(pixels, dataset))
        elif interpretation in {"RGB", "YBR_FULL", "YBR_FULL_422"}:
            image = _display_color(pixels)
        else:
            raise ImageProcessingError("This DICOM image type cannot be previewed.")
        image.thumbnail((PREVIEW_MAX_EDGE, PREVIEW_MAX_EDGE), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()
    except ImageProcessingError:
        raise
    except (AttributeError, ImportError, KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
        raise ImageProcessingError("The DICOM image could not be previewed.") from error
