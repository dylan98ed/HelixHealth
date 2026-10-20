from io import BytesIO

import pytest
from PIL import Image
from pydicom import dcmread
from pydicom.dataset import Dataset

from imaging.services import ImageProcessingError, anonymize_dicom, convert_raster


def raster_bytes(format_name="PNG"):
    image = Image.new("RGB", (2, 2), (12, 34, 56))
    image.info["patient"] = "Secret Name"
    buffer = BytesIO()
    image.save(buffer, format=format_name)
    return buffer.getvalue()


@pytest.mark.parametrize("format_name", ["PNG", "JPEG"])
def test_raster_becomes_secondary_capture_without_source_metadata(format_name):
    output = convert_raster(
        raster_bytes(format_name),
        source_format=format_name,
        birth_year=1990,
        study_year=2025,
        sex="F",
    )
    dataset = dcmread(BytesIO(output))
    assert dataset.SOPClassUID.name == "Secondary Capture Image Storage"
    assert dataset.file_meta.MediaStorageSOPInstanceUID == dataset.SOPInstanceUID
    assert dataset.file_meta.TransferSyntaxUID.is_little_endian
    assert dataset.PatientBirthDate == "19900101"
    assert dataset.StudyDate == "20250101"
    assert dataset.PatientSex == "F"
    assert dataset.PixelData == bytes((12, 34, 56)) * 4 or format_name == "JPEG"
    assert dataset.BurnedInAnnotation == "YES"
    assert b"Secret Name" not in output


def test_dicom_scrubs_identifiers_and_preserves_pixels():
    source = convert_raster(
        raster_bytes(),
        source_format="PNG",
        birth_year=1984,
        study_year=2020,
        sex="M",
    )
    dataset = dcmread(BytesIO(source))
    old_uids = (
        dataset.StudyInstanceUID,
        dataset.SeriesInstanceUID,
        dataset.SOPInstanceUID,
    )
    dataset.PatientName = "Private^Person"
    dataset.PatientID = "12345678"
    dataset.InstitutionName = "Identifying hospital"
    dataset.StudyDescription = "Secret procedure"
    dataset.PatientBirthDate = "19840520"
    dataset.StudyDate = "20200615"
    dataset.add_new((0x0011, 0x0010), "LO", "Secret private creator")
    dataset.add_new((0x0011, 0x1001), "LO", "Secret private tag")
    nested = Dataset()
    nested.PatientName = "Nested^Person"
    dataset.ReferencedStudySequence = [nested]
    buffer = BytesIO()
    dataset.save_as(buffer, enforce_file_format=True)

    output, birth_year, study_year, sex = anonymize_dicom(buffer.getvalue())
    result = dcmread(BytesIO(output))
    assert (birth_year, study_year, sex) == (1984, 2020, "M")
    assert result.PixelData == dataset.PixelData
    assert result.Rows == dataset.Rows and result.Columns == dataset.Columns
    assert result.PatientBirthDate == "19840101"
    assert result.StudyDate == "20200101"
    assert result.PatientSex == "M"
    assert not result.PatientName and not result.PatientID
    assert (0x0011, 0x0010) not in result
    assert "ReferencedStudySequence" not in result
    assert (
        result.StudyInstanceUID,
        result.SeriesInstanceUID,
        result.SOPInstanceUID,
    ) != old_uids
    assert result.file_meta.MediaStorageSOPInstanceUID == result.SOPInstanceUID
    for secret in (
        b"Private^Person",
        b"12345678",
        b"Identifying hospital",
        b"Secret procedure",
        b"Nested^Person",
        b"Secret private tag",
    ):
        assert secret not in output


def test_rejects_invalid_input():
    with pytest.raises(ImageProcessingError):
        convert_raster(
            b"not an image",
            source_format="PNG",
            birth_year=1990,
            study_year=2025,
            sex="M",
        )
    with pytest.raises(ImageProcessingError):
        anonymize_dicom(b"not dicom")
