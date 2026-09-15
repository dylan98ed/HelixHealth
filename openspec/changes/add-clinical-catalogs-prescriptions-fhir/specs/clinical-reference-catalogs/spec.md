## Purpose

Define HU-04 reference catalog management for administrative users and reliable medication and terminology selection for clinical workflows.

## ADDED Requirements

### Requirement: Administrative specialty management
Active administrative-role users SHALL create, list, edit, retire, and delete unreferenced specialties through application screens and APIs without staff privileges. Codes and names SHALL be nonblank and unique. Assigned specialties SHALL be protected from deletion, with a conflict explaining retirement as the available action. Retired specialties SHALL remain visible on existing records and unavailable for new assignments.

#### Scenario: Manage a specialty from the application
- **WHEN** a non-staff administrator starts signed out at `/`, signs in, follows Catalogs then Specialties, creates an entry, edits its name, and confirms deletion while it is unreferenced
- **THEN** each change is persisted and the deleted entry disappears from the list

#### Scenario: Delete an assigned specialty
- **WHEN** an administrator attempts to delete a specialty assigned to a professional
- **THEN** the API returns 409, the screen explains the conflict, and the professional and specialty remain unchanged
- **AND** retiring the specialty prevents new assignment without removing the existing link

### Requirement: Append-only nomenclature and medication catalogs
The system SHALL offer searchable SNOMED CT entries identified by system, version, and code, and medication entries identified by source system, version, and code. Administrative users SHALL add entries manually or upload bounded normalized JSON from third parties. Saved entries SHALL retain source/version metadata and SHALL NOT expose update, delete, or retirement operations through the application, API, or framework administration. Corrections SHALL be represented by a new source version. The application SHALL distinguish local medication codes from SNOMED CT codes and SHALL NOT claim that syntax validation proves terminology membership.

#### Scenario: Add and use a catalog entry
- **WHEN** an administrator creates a medication entry with source metadata and a doctor subsequently searches by its code or name
- **THEN** the persisted entry is available for selection with its source and version
- **AND** an administrative PATCH, PUT, or DELETE to that saved entry returns 405 without changing it

#### Scenario: Import repeated or conflicting catalog data
- **WHEN** an administrator uploads up to 500 entries and at most 2 MiB of normalized JSON
- **THEN** exact repeats of existing entries are reported as unchanged and only new entries are inserted
- **AND** a conflicting value for an existing identity or any invalid row rejects the whole import with row-specific errors and no partial additions

### Requirement: Role-restricted discovery and input handling
Catalog writes SHALL require an active administrative role and session CSRF protection. Catalog reads SHALL require an administrative role or a medical professional authorized by the existing clinical access rules. Lists SHALL support code/name search and stable pagination of 20 entries. Unauthorized requests SHALL be rejected before retrieving protected records; missing authorized targets SHALL return 404. Invalid inputs SHALL produce field errors without raw exceptions.

#### Scenario: Wrong-role writes and searchable results
- **WHEN** a doctor submits a catalog creation request or an anonymous client requests the catalog
- **THEN** access is denied with no write or protected catalog data returned
- **AND** an authorized reader can page through filtered results without losing the filter
