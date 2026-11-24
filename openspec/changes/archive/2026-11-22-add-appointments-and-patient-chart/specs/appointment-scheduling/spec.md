## Purpose

Reception manages named appointment choices and patient arrivals using the same bookable hours that administrators configure.

## ADDED Requirements

### Requirement: Daily agenda (HU-11)

Reception SHALL reach a daily agenda from the signed-in workspace, initially on the current clinic date. It SHALL identify each patient's appointment, time, professional and state in time order.

#### Scenario: Review one professional's day

- **WHEN** reception chooses a date and professional
- **THEN** the agenda shows only matching entries with distinct text for pending, confirmed, attended, canceled and absent, including a cancellation whose slot was subsequently booked again.

#### Scenario: Refresh or select an empty day

- **WHEN** a second operator records an arrival and reception refreshes, then selects a date without appointments
- **THEN** the original date shows the saved arrival and the empty date displays an explicit empty state.

### Requirement: Effective-dated availability (HU-12)

An authorized schedule administrator SHALL configure recurring hours, slot duration, effective dates and dated exceptions per eligible professional. Existing bookings SHALL retain their saved details when availability changes.

#### Scenario: Reject overlapping windows

- **WHEN** an administrator submits overlapping effective windows for the same weekday and professional, an inverted interval or a nonpositive duration
- **THEN** the invalid change is rejected and the prior configuration is retained. Adjacent valid intervals can be saved.

#### Scenario: Shorten a future schedule

- **WHEN** the administrator moves closing time earlier starting next Monday and closes another date
- **THEN** reception sees only the revised future openings and the existing confirmed booking remains on the agenda at its original time. The administrator can identify affected bookings.

#### Scenario: Reception cannot configure schedules

- **WHEN** a reception-only user attempts to save schedule configuration
- **THEN** the server denies the change.

### Requirement: Reserve, move and cancel (HU-13)

A chosen interval SHALL become occupied when its reservation is saved, including a pending one. Every successful booking, move or cancellation SHALL preserve the operator, time and change history.

#### Scenario: Concurrent selection

- **WHEN** two operators save overlapping intervals for the same professional concurrently
- **THEN** at most one conflicting reservation succeeds and the other operator sees refreshed choices. A different professional can be booked at the same time.

#### Scenario: Failed and successful move

- **WHEN** reception attempts to move a booking to an occupied interval, then chooses a free interval
- **THEN** the failed attempt preserves the original slot and the successful move frees it and occupies the newly chosen interval as a single change.

#### Scenario: Cancel a future booking

- **WHEN** reception cancels a booking in an otherwise open future interval
- **THEN** the cancellation stays on the agenda and the interval becomes available again. Repeating the submission preserves a single cancellation event.

### Requirement: Reception identity lookup and slot selection (HU-14)

Reception SHALL offer available named professional/time pairs by specialty and date with an optional professional filter. Confirmation SHALL verify an active patient using DNI and a matching second identifier.

#### Scenario: Choose between two doctors

- **WHEN** two eligible doctors have the requested opening and the patient chooses the second
- **THEN** reception can save that exact choice and the first doctor remains free. Closed, elapsed, occupied and ineligible openings are omitted.

#### Scenario: Offer before saving

- **WHEN** reception offers an opening and another operator books it before the first operator saves
- **THEN** offering leaves it free and saving the stale offer returns a conflict. Reception must select another option.

#### Scenario: Patient identity and clinical privacy

- **WHEN** a reception-only operator enters via the home page, searches an active patient's DNI and verifies the supplied date of birth
- **THEN** the operator can save a confirmed booking with only identity and contact details visible. The administrative clinical detail and patient chart deny access.

#### Scenario: Identity verification fails

- **WHEN** the patient is inactive, the date of birth mismatches or verification is omitted
- **THEN** confirmation is rejected and no confirmed booking or confirmation event is saved.

### Requirement: Manual request and confirmation (HU-15)

Reception SHALL record patient, contact, stated preference, original channel and status, and SHALL record contact outcomes on that channel. Saving an unbooked request SHALL leave the appointment inventory unchanged.

#### Scenario: No answer followed by confirmation

- **WHEN** a phone request is recorded without a slot, the first contact fails and the patient later confirms by phone
- **THEN** reopening the inbox shows the request, both outcomes with operator and time, and exactly one associated confirmed appointment.

#### Scenario: Manually recorded WhatsApp contact

- **WHEN** reception records a WhatsApp request and later records a confirmation made through that channel
- **THEN** the confirmation and linked appointment persist when the form is resubmitted. The operator manages the conversation externally.

### Requirement: Confirmed-appointment reminder (HU-17)

The system SHALL send an email with professional and local date/time for a confirmed future appointment when it falls within 24 hours. Each appointment schedule version SHALL receive at most one automatically dispatched reminder after a successful delivery.

#### Scenario: Early, threshold and late confirmation

- **WHEN** the task runs before the 24-hour boundary, exactly at it, or after an appointment is first confirmed one hour before the visit
- **THEN** there is no early message and each eligible appointment gets one message on the first eligible run. Repeating the run after success sends no further message.

#### Scenario: Schedule or state changes

- **WHEN** an appointment with a pending delivery is moved, canceled or marked attended before dispatch
- **THEN** the obsolete delivery is discarded. Only the current confirmed future schedule can generate a reminder. Pending, absent and past appointments are excluded.

#### Scenario: Delivery problem

- **WHEN** a transient transport failure occurs or the patient lacks a usable email address
- **THEN** the failure is recorded, other deliveries proceed, reception can see the problem and a definite transient failure can be retried while eligible.

### Requirement: Check-in, absence and final states (HU-18)

Reception SHALL record a verified arrival directly from pending or confirmed to attended (atendido). Absence SHALL be available once the appointment start is reached. Each successful transition SHALL have an actor and timestamp.

#### Scenario: Arrival with a pending reservation

- **WHEN** identity verification first fails and then succeeds when a patient arrives with a pending appointment
- **THEN** the first attempt preserves pending and one successful action records pending to attended. The agenda updates immediately and creates no consultation.

#### Scenario: Confirmed arrival and stale change

- **WHEN** one session records an arrival for a confirmed appointment and another tries to cancel from an older screen
- **THEN** the stored state remains attended with one arrival event and the stale action reports the current state.

#### Scenario: Record absence

- **WHEN** reception attempts to record absence for an upcoming appointment and repeats at its start
- **THEN** the early change is rejected and the later absence is recorded and visible in the agenda.
