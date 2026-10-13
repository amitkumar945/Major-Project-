# DSVV Grievance Management System — UI/UX Review

**Review date:** 12 October 2026  
**Scope:** Public website, student/staff portal, officer portal, administrator portal, shared web components, install/tracking/authentication pages, and the Flutter Android client.  
**Review type:** Review only. No application source, styles, configuration, backend, or data were changed.  
**Priority scale:** Critical = blocks a core journey or creates serious user harm; High = materially misleads or prevents a common journey; Medium = recurring usability, clarity, or responsive issue; Low = polish or consistency improvement.

## Executive summary

The project has a solid foundation: shared design tokens, a consistent blue-and-neutral palette, a real university crest in the main web shell, responsive navigation, touch-sized controls, visible keyboard focus, reduced-motion handling, role-specific navigation, table-to-card list layouts, and distinct loading, empty, and error components. Complaint status and priority badges include text as well as color, and forms generally have associated labels and field-level validation.

The most important problems are not a lack of visual styling. They are mismatches between what the interface promises and what happens next: the landing-page “Register a Complaint” button opens account registration; the Help form reports success without sending the message; and Admin Settings says the whole build has no server even though the web app is connected to the Flask API. There is also a missing logo on the app-install page.

For the core portals, key work is often surrounded by many summary tiles, charts, and repeated links. Terminology changes between “grievance,” “complaint,” “issue,” “report,” “Track,” and “My Complaints.” The web and Android experiences also differ in intake flow, login prompts, labels, and branding. The result is capable but less predictable than it should be for a university service used by students, staff, and operational officers.

No Critical issue was identified in this review.

## Review coverage and evidence

### Inspected

- Public entry and information pages: home, tracking, login, registration, password reset, install page, 404, and offline page.
- All student, officer, and admin page inventories under `frontend/student/`, `frontend/officer/`, and `frontend/admin/`.
- The shared web shell, role navigation, public navigation, form components, complaint tables/cards, filters, status badges, charts, dialogs, toasts, notifications, and state components under `frontend/assets/`.
- Representative web page renderers for student/officer/admin dashboards, complaint intake and details, tracking, complaint lists, profile, feedback, help, notifications, and system settings.
- Flutter screen inventory and representative auth, student/officer dashboard, complaint submission/list/detail, navigation-shell, state, and theme implementations under `frontend/mobile/lib/`.

### Browser checks completed

The static frontend was served locally. The public home page was checked at 768px, 916px, and 1440px viewport widths; the login page and app-install page were checked at 390px. No horizontal page overflow was observed at those tested widths. The responsive public header and the mobile login form rendered.

The app-install page displayed a broken DSVV image: its `<img>` requests `/assets/img/dsvv-logo.svg`, which is absent from the current assets folder; the browser reported HTTP 404 and `naturalWidth: 0`. The available logo asset is `dsvv-logo.png`.

### Limits

The browser pass could not sign in or render authenticated dashboards because only the static frontend server was started; the Flask API/database were not started for this review. Dashboard, complaint-list, officer/admin, and data-dependent states below are therefore **source-verified observations**, not claims of a fresh end-to-end browser reproduction. The Flutter client was inspected in source but was not run in an Android emulator or on a device. Tablet behavior of authenticated tables and native mobile screens needs follow-up validation.

Evidence labels used below:

- **Browser confirmed:** observed in the local browser pass.
- **Source confirmed:** directly evident in current markup/styles/rendering code; a live data state may still need visual confirmation.
- **Prior test report — retest:** documented in `TESTING_REPORT.md` from 6 October 2026, but not reproduced on the current worktree.
- **Needs browser/device validation:** a source-based concern whose exact visual impact depends on viewport, data, or assistive technology.

## Prioritized findings

### High

#### 1. The primary home-page action sounds like filing a report but opens account creation

- **Affected page/component:** Public home hero and final call to action — `frontend/index.html`.
- **Evidence:** **Source confirmed.** Both “Register a Complaint” links point to `/register.html`. The next screen asks the visitor to create an account; it is not the complaint form.
- **Problem:** The button label describes a completed task, while the destination is a different prerequisite. The visitor is not told in advance that sign-in or account creation is needed.
- **Impact:** Users can feel diverted or misled at the first and most important decision point, reducing trust and increasing abandonment.
- **Recommendation:** Rename the action to **Sign in or create an account to report an issue**, or label it **Create an account to report**. Keep public reference lookup as a separate, clearly explained path. Use the same phrasing in the repeated final CTA and department links.

#### 2. Help form claims a message was sent when the current UI does not send it

- **Affected page/component:** Student Help & Support — `frontend/assets/js/pages/help.js`.
- **Evidence:** **Source confirmed.** The submit handler waits briefly, resets the form, and shows “Your message has been sent to the grievance cell.” A nearby source comment says there is no mail service and the API will handle this later.
- **Problem:** The success state is not backed by a delivered or stored support request.
- **Impact:** A student may rely on a support request that never reached staff, an especially serious failure when asking for help with an unresolved grievance.
- **Recommendation:** Only show “Message sent” after a real delivery/persistence response. Until that is available, state plainly that the form is a demo or provide the working grievance-cell email/contact route as the primary action. Do not clear the entered message when no delivery occurred.

### Medium

#### 3. Admin Settings contains a stale warning that contradicts the running system

- **Affected page/component:** Admin Settings — `frontend/assets/js/pages/adminSettings.js`.
- **Evidence:** **Source confirmed.** The page says “This build has no server. Authentication and AI classification are simulated in the browser,” while the current frontend README describes a Flask API integration, the auth and complaint services call the API, and the settings page itself stores its settings in browser storage.
- **Problem:** The warning combines inaccurate build-wide claims with a narrower true limitation (these settings are browser-local).
- **Impact:** Administrators may doubt whether the whole portal is live, misunderstand which settings take effect, or assume their changes apply to other users.
- **Recommendation:** Replace the global prototype warning with precise per-setting scope: identify which settings are local to this browser, which are API-backed, and which are not yet active. Add a concise “Saved on this device” or equivalent confirmation next to local-only settings.

#### 4. App-install page shows a broken university logo

- **Affected page/component:** Install page header — `frontend/app.html`.
- **Evidence:** **Browser confirmed.** The image source is `/assets/img/dsvv-logo.svg`; that file is absent, and the local browser returned a 404. `frontend/assets/img/dsvv-logo.png` exists.
- **Problem:** The page displays a missing image where the university identity should appear.
- **Impact:** The install/download page looks unfinished and less trustworthy, particularly because users are deciding whether to install the university portal.
- **Recommendation:** Point this page at the available crest asset and check its rendered size, alt text, and contrast against the header background. Verify the icon/crest references across the install page and PWA metadata as a single asset audit.

#### 5. Mobile web authentication loses the university/product identity

- **Affected page/component:** Login, registration, and password-reset layouts — `frontend/login.html`, `frontend/register.html`, `frontend/forgot-password.html`, and `frontend/assets/css/layout.css`.
- **Evidence:** **Browser confirmed at 390px.** The auth aside, which contains the crest and product identity, is hidden below 1024px. The login form itself has no compact logo; the mobile screenshot begins with “Back to website” and then the form.
- **Problem:** The strongest university branding disappears on the screen most likely to be reached from a phone.
- **Impact:** New or redirected users have less assurance that they are signing into the official DSVV service; login, registration, and reset screens feel detached from the public site.
- **Recommendation:** Keep a compact DSVV crest and product name above the auth panel on small screens. Use one shared identity treatment across login, registration, reset, and the native app.

#### 6. Student/staff registration offers one mixed department/course list

- **Affected page/component:** Web registration form; corresponding Flutter registration screen — `frontend/assets/js/pages/register.js`, `frontend/mobile/lib/screens/auth/register_screen.dart`.
- **Evidence:** **Source confirmed.** The form first asks whether the registrant is a Student or Staff member, but both receive the same “Department / Course” selector containing a mixture of degree courses, departments, and “Other Department.”
- **Problem:** A staff member may not find their administrative unit, while students may be unsure whether to choose a course or a department.
- **Impact:** People can select a catch-all or incorrect organization, creating confusing profile details and making later support or routing harder.
- **Recommendation:** Keep the same registration journey but make the selector’s label and choices adapt to account type. Use student course/program choices for students and actual organizational departments for staff; explain the “Other” option if it remains necessary.

#### 7. Intake language and the web wizard make an automatic step feel like user work

- **Affected page/component:** Student complaint form and Help FAQ — `frontend/assets/js/pages/newComplaint.js`, `frontend/assets/js/pages/help.js`, `frontend/mobile/lib/screens/student/new_complaint_screen.dart`.
- **Evidence:** **Source confirmed.** The web form presents five steps, including a separate “Check”/AI-analysis step, and the FAQ tells users to “run the AI analysis.” The Flutter client instead uses one scrolling form and describes classification as automatic.
- **Problem:** The student is asked to navigate an extra step for a system-run operation, and web/mobile guidance describes the same process differently.
- **Impact:** The form feels longer than its actual user-input requirements and users may wonder whether the AI step is optional, required, or a decision they must make.
- **Recommendation:** Keep the existing fields and review step, but describe classification as an automatic status within the flow rather than an action the user must “run.” Keep concise progress guidance on web and equivalent explanations in Android. Clearly explain any location or evidence requirement at the point it applies.

#### 8. Dashboard pages put summaries and charts ahead of the next useful action

- **Affected page/component:** Student, officer, and admin dashboards — `frontend/assets/js/pages/studentDashboard.js`, `officerDashboard.js`, and `adminDashboard.js`; admin analytics — `adminAnalytics.js`.
- **Evidence:** **Source confirmed; authenticated layouts not browser-rendered.** The student dashboard puts seven counters and three charts before its focus/recent-work sections and includes six quick links. Officer dashboard includes up to eight counters, multiple charts, performance figures, and a timeline. Admin dashboard includes eight metrics, four chart cards, department performance, and latest complaints; Analytics adds a longer chart sequence.
- **Problem:** Repeated metrics and analytics compete with the operational task. Student quick links duplicate destinations already present in sidebar/mobile navigation; officers need actionable work, and admins need exceptions, before broad performance summaries.
- **Impact:** Users scan and scroll longer to find what needs action; urgent or overdue cases can have less prominence than aggregate counts.
- **Recommendation:** Lead with a compact role-specific “Needs attention” or “Your next actions” block and recent/actionable complaints. Retain all metrics and charts but move secondary analytics lower or into a clearly named expandable section. Reduce the visual weight of duplicate dashboard shortcuts without removing any route.

#### 9. “My Complaints,” “Track Complaint,” “Assigned Complaints,” and “Department Queue” need clearer distinctions

- **Affected page/component:** Student/officer navigation, dashboard quick links, and mobile navigation — `frontend/assets/js/components/navigation.js`, `studentDashboard.js`, and Flutter shell files.
- **Evidence:** **Source confirmed.** Students see both “My Complaints” and “Track Complaint,” with both repeated in quick links; public tracking is a reference-number lookup. Officers see “Assigned Complaints” and “Department Queue.” The mobile interface also uses “Alerts” where the web shell says “Notifications.”
- **Problem:** Similar labels do not explain ownership or when to use each destination; the same task is repeated in multiple navigation areas with slightly different names.
- **Impact:** Students may not know whether they need a reference number to view their own reports. Officers may confuse personal assignments with department-wide work. Naming differences weaken web/mobile familiarity.
- **Recommendation:** Use one consistent student-facing noun such as **Reports** or **Complaints**. Explain that **My complaints** is the signed-in list and **Track by reference number** is public lookup. Rename officer destinations to make ownership explicit (for example, **My assigned work** and **Department work**). Use **Notifications** on web and mobile.

#### 10. Complaint table mode switches at a breakpoint that may be too early for the available content width

- **Affected page/component:** Shared complaint table — `frontend/assets/js/components/complaintTable.js`, `frontend/assets/css/pages.css`, `frontend/assets/css/components.css`, and `frontend/assets/css/layout.css`.
- **Evidence:** **Source confirmed; 1200px transition needs browser validation.** The table is at least 860px wide; mobile cards are hidden at 1200px, exactly where the 272px desktop sidebar appears. Admin lists can show eight data columns plus an action column.
- **Problem:** At the 1200px transition, the remaining main-column width is only about 880px after the 272px sidebar and page padding—only slightly above the table's 860px minimum. A dense admin table can be cramped or require horizontal scrolling just as the mobile-card treatment disappears.
- **Impact:** At small desktop/larger tablet widths, important complaint fields and actions can become difficult to compare or reach.
- **Recommendation:** Validate the complaint list at 1024, 1199, 1200, and 1280px with realistic long IDs/titles. Switch table/card mode based on usable content width, not only the viewport; alternatively provide a compact admin column set with secondary information retained in complaint details.

#### 11. Dashboard statistics and performance numbers need reporting context

- **Affected page/component:** Admin dashboard and analytics — `frontend/assets/js/pages/adminDashboard.js`, `adminAnalytics.js`; officer performance panel — `officerDashboard.js`.
- **Evidence:** **Source confirmed.** Admin metrics include satisfaction rate, average resolution days, and totals; officer metrics include resolution rate, average days, and rating. The dashboard labels do not consistently expose the reporting period or calculation basis.
- **Problem:** Percentage and average figures look precise but do not consistently explain the time window, denominator, or whether they cover all historical complaints.
- **Impact:** Administrators and officers can misread changes or compare unlike periods when making operational decisions.
- **Recommendation:** Display a visible “as of”/reporting-period label and concise metric definitions (for example, what counts as resolved and which feedback responses form the satisfaction denominator). Keep the displayed data unchanged unless the underlying analytics support a different window.

#### 12. Dashboard/table skeletons are not announced as loading states to assistive technology

- **Affected page/component:** `skeletonCards()` and `skeletonTable()` — `frontend/assets/js/components/ui.js`; used by all three dashboards and complaint lists.
- **Evidence:** **Source confirmed; assistive-technology behavior needs validation.** The shared `loadingState()` has `role="status"`, but the skeleton-card/table renderers do not add a status label or an `aria-busy` state.
- **Problem:** Sighted users see placeholder blocks, but a screen-reader user may get no indication that dashboard/list data is being fetched.
- **Impact:** The page can seem blank or stalled until the request completes, especially on a slow connection.
- **Recommendation:** Announce a concise “Loading dashboard/complaints” status and mark the changing content region `aria-busy="true"` while skeletons are visible; clear it when success or error content replaces the placeholder.

#### 13. Public hero image depends on a remote thumbnail rather than a maintained campus asset

- **Affected page/component:** Home hero photograph — `frontend/index.html`.
- **Evidence:** **Source confirmed; image rendered in browser.** The hero uses an external Google thumbnail URL; the browser loaded a 659px-wide image while the rendered hero was wider at desktop.
- **Problem:** The prominent image is externally hosted and is supplied as a small thumbnail. Its availability, crop, and quality depend on a third party rather than the project’s release assets.
- **Impact:** The largest branded surface may be soft at wide viewports or change/disappear independently of the university site. The existing fallback background avoids a blank region but is less informative.
- **Recommendation:** Use an approved, appropriately sized campus photograph served from project/CDN assets, with a focal-point crop tested at phone, tablet, and desktop widths. Keep the existing fallback behavior.

### Low

#### 14. Mobile login role cards leave a visually orphaned third option

- **Affected page/component:** Web login role selector — `frontend/assets/css/components.css` and `frontend/assets/js/pages/login.js`.
- **Evidence:** **Browser confirmed at 390px.** The role-card grid fits two cards on the first row and leaves “Administrator” alone on the second row.
- **Problem:** The last option looks unbalanced and can be mistaken for a different grouping.
- **Impact:** Minor visual inconsistency on the mobile login screen.
- **Recommendation:** At narrow widths, show the role choices as a consistent single-column list, or use another layout that gives each role equal visual weight.

#### 15. Small metadata labels and chart annotations are below comfortable reading size

- **Affected page/component:** Student dashboard detail chips, complaint progress labels, chart ticks, and helper metadata — `frontend/assets/css/pages.css`.
- **Evidence:** **Source confirmed; legibility should be checked on real devices.** Several secondary labels are 11px; the base extra-small token is 13px.
- **Problem:** Small labels carry supporting information such as profile labels and chart ticks.
- **Impact:** These details are harder to read on mobile, at high zoom, and for users with low vision.
- **Recommendation:** Keep tertiary information visually secondary but target at least 12–13px where space permits. Preserve chart tables as an alternative and verify text scaling at 200%.

#### 16. Web and Android sign-in/branding conventions differ

- **Affected page/component:** Web login and mobile login — `frontend/assets/js/pages/login.js`, `frontend/mobile/lib/screens/auth/login_screen.dart`, and `frontend/mobile/lib/core/theme/app_theme.dart`.
- **Evidence:** **Source confirmed; native screen not device-rendered.** Web login asks users to choose Student/Staff, Officer, or Administrator and accepts a university email; Android accepts “Email or User ID” without a role picker and displays a generic gavel mark instead of the web crest.
- **Problem:** The same service uses different identity marks, credential instructions, and role-selection expectations between clients.
- **Impact:** A returning user may be unsure which credentials apply or whether the app is the same official service.
- **Recommendation:** Align logo/product naming and clearly explain any intentional credential differences. Keep role detection convenient on mobile, but ensure both clients communicate supported identifiers consistently.

## Previously reported interaction issues — retest before treating as current

The following items are documented in `TESTING_REPORT.md` from 6 October 2026. They affect user experience, but they were **not reproduced during this source/browser review** and may have changed in the current worktree:

1. **Duplicate status update, timeline entry, notification, and success toast** after one officer status change. Re-test once and verify the visible confirmation and timeline each reflect one action.
2. **Duplicate confirmation dialogs** when opening resolution and escalation flows. Re-test the current dialog/action wiring before changing the UI.
3. **Attachment Remove control missing after returning to the evidence step** in the web complaint wizard. Re-test selecting, navigating away/back, and removing a file; the control must remain visible and keyboard reachable.

Treat these as **historical reports requiring current reproduction**, not as newly verified defects.

## Strengths to preserve

- Shared tokens and common button, card, badge, form, filter, table, and state components reduce visual drift.
- The public home and login pages were responsive at the checked widths; no horizontal overflow appeared on those pages in this browser pass.
- Web styles include visible keyboard focus, a skip link, reduced-motion handling, and touch-target sizing. The portal drawer includes focus handling and an Escape key path.
- Complaint status and priority badges include text, not color alone. Complaint lists have sortable headers, filters, pagination, and mobile card alternatives.
- The UI distinguishes empty, loading, and error states in shared components; empty states often offer a relevant next action, and errors generally have a retry path.
- The tracking page explains the reference-number format and intentionally withholds personal contact details from the public lookup.
- The app-install page correctly explains that a local `localhost` QR cannot be scanned from another device and that an APK has not yet been published. Those messages are preferable to a misleading QR or dead APK link.

## Recommended visual direction

Aim for a calm, official university service rather than a generic analytics product:

1. **One clear action per role:** students see “Report an issue” and their recent reports; officers see overdue/urgent assigned work; administrators see overdue, urgent, and unassigned exceptions.
2. **A stable visual hierarchy:** consistent title and action placement, one spacing scale, restrained shadows, and fewer equally prominent tiles. Preserve all charts and administrative controls, but place secondary analysis after work queues.
3. **Plain, consistent language:** choose a primary student-facing term (recommended: “report” or “complaint”), reserve “grievance” for formal/policy contexts, and explain status transitions in terms of what happens next.
4. **Trustworthy university identity:** use the same approved crest/product lockup on desktop, mobile web, Flutter, and install surfaces; use locally controlled, correctly sized imagery.
5. **Actionable case cards:** make reference, short title, status, department/owner, due date, and next action easy to scan. Keep detailed history, remarks, evidence, and maps on the complaint detail page.
6. **Accessible state feedback:** announce loading, preserve typed content on errors, explain recovery steps, and only show success after the action has actually completed.
7. **Responsive behavior by available space:** test real table content, long university/department labels, multi-button headers, charts, filters, bottom navigation, and dialogs at breakpoints rather than relying only on a single phone/desktop snapshot.

## Prioritized improvement plan

### Phase 1 — Correct the user promise and trust cues

- Clarify the home-page reporting CTA and account prerequisite.
- Stop the Help form from showing an unverified delivery success.
- Correct the Admin Settings status copy so it describes only the actual limits of each setting.
- Repair the app-install page crest reference and standardize the mobile login identity.

### Phase 2 — Reduce friction in frequent journeys

- Clarify the student public tracking versus signed-in complaints distinction, and officer personal versus department queue.
- Align role, status, navigation, and complaint terminology across web and Android.
- Simplify how the automatic department/AI check is explained while retaining all current form fields, validation, and review controls.
- Reorder dashboards so role-specific actions and exceptions precede charts and secondary shortcuts.

### Phase 3 — Validate dense and assistive states

- Test authenticated complaint lists at 1024–1280px, including long text, filters, sorting, actions, and horizontal scrolling.
- Add announced loading status for skeleton-based dashboard/table loading.
- Confirm metric periods/definitions, small label legibility, focus order, and 200% zoom.
- Re-test the three historical interaction observations and exercise Flutter screens on representative Android sizes.

All recommendations are UI, copy, or validation proposals. They do not authorize removal of routes, data, permissions, or existing features.
