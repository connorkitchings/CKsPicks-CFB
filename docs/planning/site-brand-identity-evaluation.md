# Brand Identity Evaluation: Moving from "CK's Picks" to "Hashmark"

- **Status:** Evaluation Complete · Decision Deferred (Candidate Winner Selected)
- **Date:** 2026-10-24
- **Primary Selected Brand:** **Hashmark** / **Hashmark CFB**
- **Strongest Runner-Up:** **Snapline** / **Snapline CFB**
- **Personal Fallback (in reserve):** **CK_Rank**
- **Target Implementation:** Future release (brand constant parameterization first, assets/copy to follow)

---

## 1. Executive Summary & Purpose

The purpose of this evaluation was to establish a permanent brand identity for the college football platform, replacing the working name **"CK's Picks"**.

While "CK's Picks" served as a convenient working title during early model development, the term **"Picks"** carries negative connotations in the sports data space—evoking commercial handicapper "touts," subscription tipster services, or casual betting pick'ems. In reality, this platform is an engineered, quantitative college football forecasting and ratings system featuring:
- **V5 Blitzkrieg:** Possession-based ratings, Ridge regression bridge, and drive-level efficiency.
- **Opponent Adjustments & Point-in-Time Integrity:** Strict pre-kickoff provenance, no future leakages, and transparent YTD performance tracking against market lines.
- **Visual Analytics:** Interactive scatter plots, net success distributions, matchup unit tables, and team resumes (SOR/SOS).

The objective was to identify a brand identity that commands immediate credibility among college football analysts, data scientists, and serious fans.

---

## 2. Competitive Landscape & Community Archetypes

We analyzed the naming conventions across the independent college football analytics and modeling landscape:

| Peer / Creator | Model / Site Name | Strategy | Analysis |
|---|---|---|---|
| **Brian Fremeau** | **FEI** (*Fremeau Efficiency Index*) | Institutional Acronym | Formal, authoritative; feels like a government or academic benchmark. |
| **Bill Connelly** | **SP+** (*Success Rate & Points*) | Formula / Pure Math | Sounds like a premium financial rating (S&P) or rigorous math equation. |
| **Kelley Ford** | **KFord Ratings** | Personal Name + Output | Simple, transparent, builds personal authority. |
| **Robby Greer** | **Beta_Rank** | Computer Science / Data Syntax | Underscore syntax (`_`) and statistical parameter ($\beta$) signals developer roots. |
| **PearRatings** | **PearRatings** | Distinctive, Concrete Object | Unexpected, memorable, friendly, consumer-app aesthetic. |
| **Iron CFB** | **Iron CFB** | Material / Physical Grit | Connotes the line of scrimmage, toughness, and unyielding empirical data. |
| **Parker Fleming** | **CFB Graphs** | Delivery / Visual Output | Immediately tells the user to expect visual data science, charts, and plots. |

---

## 3. Evaluation Criteria & Filtering Rules

Through structured feedback, we applied the following non-negotiable boundaries:

1. **No Algorithmic Lock-In (Discarded Pure Math / Engine Names):**
   - Names like *Ridge_Rank* or *Possession CFB* were rejected because modeling methodologies evolve. The brand must not be tethered to one mathematical transform (Ridge) or data unit (possession).
2. **No Generic or Overly Aggressive Military Tropes:**
   - *Blitzkrieg Analytics* and *Blitz CFB* were rejected. "Blitzkrieg" carries excessive historical baggage, and "Blitz" is cliché and overused in sports media.
3. **No Surname / Personal Focus (Except `CK_Rank` in Reserve):**
   - Full surname options (*Kitchings CFB*) were set aside. If a personal brand is ever required, **`CK_Rank`** remains the sole approved fallback.
4. **The Target Sweet Spot:**
   - Tangible, evocative, football-grounded physical nouns and field geometry (analogous to *Pylon*, *Iron CFB*, and *PearRatings*).

---

## 4. Due Diligence & Conflict Research

We conducted competitive searches across sports analytics, technology, and sports betting for top contenders:

### Chalkline / The Chalkline ⚠️ (High Conflict / Disqualified)
- **Direct Collision:** **Chalkline Sports** (`chalkline.com`) is an established B2B sports betting technology and customer-acquisition analytics provider (creator of the *BettorBI* platform).
- **Secondary Collision:** **Chalk Line** is a famous heritage streetwear apparel brand known for licensed sports jackets.
- **Verdict:** Disqualified due to direct commercial overlap in sports betting software.

### Pylon / Pylon CFB ⚠️ (Crowded Field)
- **Prior Analytics Presence:** **Inside the Pylon (ITP)** was a prominent, highly regarded football film and advanced analytics publication (founded by Mark Schofield and Chuck Zodda; pioneered EPA and scheme analysis).
- **Secondary Presence:** **Pylon 7v7** is the dominant national high school 7-on-7 tournament brand; **Pylon Sports** (`pylonsports.com`) is a coaching film dashboard platform.
- **Verdict:** Viable as `Pylon CFB`, but heavily trafficked across football culture.

### Hashmark / Hashmark CFB 🟢 (Wide Open / Clear Winner)
- **Landscape:** No recognized college football power rating, public analytics model, or betting dashboard uses *Hashmark*.
- **College Football Significance:** Unlike the NFL (which uses narrow 18'6" hashmarks), **college football is uniquely defined by its wide hashmarks (40'0" apart)**. Hashmark positioning dictates college offensive spacing, boundary-vs-field leverage, short-side route trees, and field-goal difficulty.
- **Verdict:** Unencumbered trademark/domain runway and deep, authentic gridiron resonance.

### Snapline / Snapline CFB 🟢 (Clean Runner-Up)
- **Landscape:** Only minor collisions (a simulated play-money game and a fantasy overlay extension). Zero presence in real-world college football analytics.
- **Double Meaning:** Combines the "snap" of the ball with a "snap line" (the chalk line carpenters snap to mark absolute truth).
- **Verdict:** Strong, modern, punchy runner-up.

---

## 5. The Winning Direction: **Hashmark**

### Why Hashmark Won
1. **Uniquely College Football:** Hashmarks in college football fundamentally shape how the game is played and analyzed, far more than in the NFL.
2. **Authoritative & Permanent:** It sounds like a permanent institution (like *The Athletic*, *FiveThirtyEight*, or *Massey*), not a transient tipster tool.
3. **Clean Visuals:** Centered in the mobile app bar (`HASHMARK` or `HASHMARK CFB`), it is symmetrical, readable, and bold.
4. **Broad Semantic Scope:** It covers spreads/totals (Games), team efficiency (Ratings), scatter plots and trajectories (Graphs), and methodology (Model).

### Formatting Variations
- **Primary Brand Display:** **`Hashmark`** (or **`Hashmark CFB`** for search/social clarity)
- **Editorial Voice:** *"According to the Hashmark ratings..."* / *"Hashmark post-Week 8 projections..."*
- **Mobile Header:** Centered `HASHMARK` wordmark.

---

## 6. Implementation Strategy (Deferred)

The site will not switch immediately. To ensure a zero-friction migration when the owner authorizes the cutover:

1. **Brand Parameterization:** In `web/src/lib/constants.ts` (or `chart-config.ts`), declare:
   ```typescript
   export const APP_NAME = "CK's Picks CFB"; // Future: "Hashmark" or "Hashmark CFB"
   export const APP_SHORT_NAME = "CK's Picks"; // Future: "Hashmark"
   ```
2. **Decouple UI Components:** Wire `AppBar.tsx`, `Header.tsx`, `layout.tsx` metadata, and footer copyright to use `APP_NAME` instead of hardcoded strings.
3. **Cutover Execution:** When ready, update `APP_NAME`, review SEO metadata/OpenGraph tags, and register relevant domains/social handles (`hashmarkcfb.com`, `@hashmarkcfb`).
