# User Journeys

### Journey 1: Sara — The Operations Manager (Repetitive Professional Workflow)

Sara has been submitting the same vendor compliance form every month for two years. It's a 15-field portal with dropdowns, date fields, and an attachments section that always seems to move. She knows every field by memory — and that's exactly what makes it maddening. It's not hard. It's just slow, manual, and beneath her.

She opens ARIA and says: *"Fill out the monthly compliance form on the supplier portal. I'll give you the values as you go."*

ARIA opens the portal. The thinking panel activates — she can see it scanning the page, identifying fields, building a step plan. *"I can see 14 form fields. Here's what I'll do: I'll fill each field in order and pause before submitting."* It starts moving. Vendor name, filled. Category code, filled. She watches the panel update in real time.

On the attachments field, ARIA pauses: *"I need the certificate file path — I don't have that. Can you provide it?"* Sara uploads the file. ARIA continues.

When it reaches the Submit button, it stops: *"This will submit the form to the vendor portal. This action cannot be undone — shall I proceed?"* Sara says *"Yes, submit."* The form goes through.

She looks at the audit log — every field, every value, every screenshot, timestamped. Next month, she'll hand this to an intern with the log as the guide.

**Requirements revealed:** Voice task input, Planner step plan display, Executor form-filling, mid-task user input request, destructive action guard, audit log.

---

### Journey 2: James — The College Student (Research Aggregation)

James is comparing five hotels for a family trip. He has five tabs open and a blank Google Doc. He's been copying and pasting for 20 minutes. The prices don't line up, the amenity lists use different words, and he's lost track of which tab he's on.

He opens ARIA and says: *"Go through these 5 hotel pages and collect the nightly price, star rating, free breakfast availability, and pool availability into a list."*

ARIA starts on the first tab. The thinking panel shows it reading the page — *"I can see the price listed as $142/night in the booking summary section."* It moves through each page methodically, narrating what it finds. James watches, occasionally correcting: *"Wait, that's the weekend price — I need weekday."* ARIA pauses, re-reads the page, finds the weekday rate.

Five pages later, ARIA presents a clean comparison list in the chat panel. James copies it into his doc.

**Requirements revealed:** Voice task input, multi-step Executor navigation, live thinking panel, voice barge-in/correction mid-task, structured output display.

---

### Journey 3: Margaret — The Retired Teacher (Low-Tech Confidence, High-Stakes Form)

Margaret needs to complete her Medicare supplemental insurance application online. The form is long, the language is bureaucratic, and she's already made one mistake that required starting over. Her daughter set up ARIA for her.

She clicks the microphone and says slowly: *"Help me fill in my Medicare insurance application on this site."*

ARIA responds warmly in voice: *"I can see the application. It has 8 sections. I'll go through them one by one and ask you for each piece of information I need."* The thinking panel shows each section as ARIA reaches it. Margaret can see exactly where they are in the form.

ARIA reads each field aloud and waits for her answer. When it reaches a field it can infer from context — her name, already shown on the page header — it fills it automatically and narrates: *"I've filled in your name from the page — does that look right?"*

Before submitting: *"I'm about to submit your application. Once submitted, this cannot be changed. Shall I go ahead?"* Margaret says *"Yes please."*

She feels none of the anxiety she had before. The audit log shows her exactly what was submitted — she screenshots it for her records.

**Requirements revealed:** Voice task input, voice narration throughout, conversational mid-task data collection, destructive action guard with voice confirmation, audit log.

---

### Journey 4: Ravi — The Startup Founder (QA / Power User)

Ravi is 2 hours from a product launch. He needs to walk through the entire checkout flow — add to cart, enter shipping, apply a promo code, confirm payment — and verify every step works on the staging environment. His QA person is sick. He's doing it himself.

He opens ARIA and types: *"Go through my checkout flow at staging.myapp.com. Add the item called 'Pro Plan', use the test promo code LAUNCH20, enter shipping address [X], and verify the order confirmation page shows the correct discounted total."*

ARIA starts. The thinking panel shows it navigating each step, highlighting the element it's about to interact with. It applies the promo code — and the thinking panel shows: *"Confidence low — the discount field shows $0 instead of the expected 20% reduction. This may be a bug."* It pauses and flags the issue to Ravi.

Ravi leans in: *"Good catch. Stop there."* He fixes the promo code logic in his codebase, restarts staging, and runs ARIA again. This time it completes cleanly.

The audit log is a complete record of both runs — screenshots, steps, the flagged anomaly. He pastes the second run into the launch ticket as QA evidence.

**Requirements revealed:** Text task input, Planner structured step plan, Executor navigation + form interaction, live confidence scoring in thinking panel, voice/text barge-in stop, audit log as QA artifact.

---

### Journey 5: Leila — The Travel Blogger (Complex Multi-Step Research + Booking)

Leila needs to book a Cairo → Lisbon flight for next Friday — one stop maximum, cheapest available. She's on three booking sites simultaneously and losing track of which results are comparable.

She opens ARIA: *"Find the cheapest flight from Cairo to Lisbon next Friday with one stop max. Check Google Flights, Skyscanner, and Kayak. Tell me the top 3 options before booking anything."*

ARIA opens Google Flights first. The thinking panel shows it setting the origin, destination, and date fields, filtering by stops. It extracts the top results and narrates: *"On Google Flights, the cheapest one-stop option is EgyptAir via Istanbul at $340."* It moves to Skyscanner, then Kayak.

After all three sites, ARIA surfaces a comparison: *"Cheapest overall: $298 on Skyscanner via Madrid. Would you like me to proceed to booking?"* Leila says *"Yes, the Skyscanner one."*

ARIA navigates to the booking flow. Before entering payment: *"I've reached the payment step. This is an irreversible purchase of $298. Shall I proceed?"* Leila confirms.

**Requirements revealed:** Voice task input, multi-site navigation by Executor, structured results aggregation and display, user confirmation before proceeding, destructive action guard on purchase.

---

### Journey 6: Chris — The Content Creator (Repetitive Upload Workflow)

Chris uploads a new video every week to three platforms. Same process every time: title, description, tags, thumbnail, category. He's done it 80 times. It's 20 minutes of his life he'll never get back — every single week.

He opens ARIA and pastes his metadata doc, then says: *"Upload my latest video to YouTube. The file is on my desktop. Use the title, description, and tags from this doc."*

ARIA opens the YouTube upload interface. The thinking panel shows it locating the upload button, dragging the file, then systematically filling each metadata field from the doc. Chris watches, doing something else.

The thinking panel flags: *"The tags field has a 500-character limit. Your provided tags exceed this. I've trimmed to fit — want to review before I continue?"* Chris glances over: *"Yeah that's fine, continue."*

Before publishing: *"I'm about to publish this video publicly. This will make it live immediately. Confirm?"* Chris says *"Confirm."*

**Requirements revealed:** Text + document input, Executor file interaction and form-filling, constraint detection and flagging in thinking panel, user micro-confirmation mid-task, destructive action guard on publish.

---

### Journey Requirements Summary

| Capability | Journeys That Require It |
|---|---|
| Voice task input | Sara, Margaret, Leila, Chris (partial) |
| Text task input | Ravi, Chris, James (partial) |
| Planner step plan display | All journeys |
| Executor browser/form actions | All journeys |
| Live thinking panel with confidence | All journeys — Ravi specifically needs confidence scoring |
| Voice narration | Margaret (critical), Sara, Leila |
| Mid-task user input request | Sara (file upload), Margaret (field data), Chris (tag review) |
| Voice barge-in / interruption | James (correction), Ravi (stop), Sara (implicit) |
| Destructive action guard | Sara (submit), Margaret (submit), Leila (purchase), Chris (publish) |
| Structured output / results display | James (comparison list), Leila (flight options) |
| Audit log | Sara (compliance record), Ravi (QA evidence), Margaret (personal record) |
