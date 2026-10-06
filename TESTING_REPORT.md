# DSVV Grievance Management System — Testing Report

**Testing date:** 6 October 2026  
**Environment:** Local development application and local MongoDB database  
**Testing method:** Manual end-to-end testing through the existing browser UI, supplemented by the backend automated test suite

## 1. Testing overview

Testing used the locally running DSVV Grievance Management System. Dummy accounts and grievances were created using the system’s registration, administration, and grievance-submission screens. The test records were stored in the local `grievance_management` database. Existing records were not intentionally changed.

The scope covered representative student/staff, administrator, and officer journeys, from registration and grievance submission through departmental handling, resolution, feedback, and notifications.

## 2. Dummy data used

Four test accounts were created:

- Student: UI Test Student Aurora
- Staff: UI Test Staff Bramble
- Administrator: UI Test Administrator
- Officer: UI Test Officer, assigned to Nirman Vibhag

Four grievances were submitted:

| Reference | Category and department | Priority | Status at end of testing | Additional test data |
|---|---|---|---|---|
| `DSVV-GRV-2026-00075` | Water — Jal Kal Vibhag | High | Pending | Dummy description and a PDF evidence attachment |
| `DSVV-GRV-2026-00076` | Electricity — Vidyut Vibhag | Medium | Assigned | Dummy description |
| `DSVV-GRV-2026-00077` | Computer/Lab — MCA Lab / Computer Lab | Urgent | Escalated | Dummy description; priority changed and grievance escalated by an administrator |
| `DSVV-GRV-2026-00078` | Building — Nirman Vibhag | Medium | Resolved | Dummy description, officer remark, resolution notes, and 5-star feedback |

The entries and descriptions were explicitly dummy test data. Grievances were routed to their matching departments through the application’s automatic classification workflow.

## 3. Functionalities tested

- Student and staff account registration and sign-in
- Administrator and officer account creation and sign-in
- Grievance submission with description, category, campus location, and attachment
- Automatic department and priority analysis, including suggested officer and possible-duplicate display
- Student complaint tracking and complaint details
- Officer dashboard, assigned grievance access, remarks, and status updates
- Administrator complaint list, priority change, and escalation
- Resolution submission and resolution confirmation
- Student feedback submission and rating display
- In-app notification creation and notification list
- Local API health endpoint and MongoDB connectivity
- Backend automated regression tests

## 4. Test results

The representative UI workflows completed successfully: accounts could be created and signed in; grievances were submitted with generated references and displayed in complaint views; the officer could add a remark and update status; the administrator could change priority and escalate; and an officer could resolve a grievance, after which feedback could be submitted. In-app notifications were visible to the test user.

The UI also surfaced similar existing grievances during the Computer/Lab submission test. The tester reviewed the suggestions and explicitly continued because the dummy report was intended to represent a separate issue.

The submission workflow did not provide a “Rejected” status option. Therefore, a rejected grievance was not created. The tested final status mix was Pending, Assigned, Escalated, and Resolved.

## 5. Issues and bugs found

1. **Duplicate status updates:** A single officer status update produced duplicate timeline entries and duplicate notifications. Duplicate success toasts were also observed.
2. **Duplicate action dialogs:** Opening the resolution flow displayed multiple identical dialogs. The escalation flow also displayed duplicate confirmation dialogs.
3. **Attachment removal after navigating back:** After selecting an attachment and navigating back to the attachment step, the restored file entry did not have a Remove control. Restarting the submission was required to discard that draft attachment.
4. **Rejected status unavailable:** “Rejected” was not present in the available system status options, so that requested status could not be included in the test data.

These are observations from testing only; no fixes or source changes were made as part of this report.

## 6. Backend test results

The backend automated test suite completed with **309 passed and 1 skipped**.

## 7. API and database status

The local API health response reported that the API was running and the database was reachable. The local MongoDB instance was available during testing, and UI-created records were returned in the application’s user and complaint views.

## 8. Email status

Email was **not configured** in the local environment (`email: false`). External email delivery was not tested. In-app notifications were tested and observed.

## 9. Final testing conclusion

The core representative grievance-management journey worked end-to-end in the local environment, and the backend regression suite passed with one skipped test. Testing also identified duplicate status/notification behavior, duplicate dialogs, an attachment-removal usability issue when returning to the upload step, and the absence of a Rejected status option. Email delivery remains unverified because local email configuration was unavailable.

This report records the results already obtained. It does not make or imply any changes to source code, application behavior, or database records.
