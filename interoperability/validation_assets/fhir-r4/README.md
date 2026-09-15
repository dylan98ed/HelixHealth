# FHIR R4 offline validation assets

`fhir-all-xsd.zip` was downloaded from the official HL7 FHIR R4 publication
at `https://hl7.org/fhir/R4/fhir-all-xsd.zip` on 2026-09-15. The checked-in
schemas identify themselves as FHIR R4 `4.0.1` and include the copyright and
redistribution notice supplied by HL7.

Runtime validation reads `fhir-all.xsd` and every imported schema only from
this directory. The XML parser disables DTD loading, entity resolution, and
network access. The independent model validation dependency is
`fhir.resources[xml]==6.4.0`, pinned with `pydantic==1.10.21` because that
R4 release otherwise resolves to incompatible Pydantic v2. XML handling uses
`defusedxml==0.7.1` and `lxml==6.1.3`. These exact versions were verified on
Python 3.13.15 on 2026-09-15.

No runtime schema, profile, terminology, or reference lookup may access the
network. The narrower HelixHealth exchange profile remains to be added by
task 3.1.
