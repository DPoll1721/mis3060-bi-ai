# Prompt Engineering Comparison

# Strategy 1: Zero-shot

# Complete prompt sent:
"What should a BI dashboard for a loan portfolio committee include, and why?"

# First 150 words of Claude's response:
"A loan portfolio committee dashboard needs to answer three questions at a glance: how big and how good is the book, where is risk concentrating, and are trends moving the wrong way. Here's how I'd structure it. Portfolio overview. Total outstanding balance, number of loans, and weighted average yield, broken out by product line or business segment, each shown against prior month and prior year. This is the "state of the book" section committees expect first, and trend lines matter more than the point-in-time number because a committee's job is to catch inflection points early. Credit quality and delinquency. Delinquency buckets (30/60/90+ days past due) as both dollar amounts and percentage of portfolio, migration analysis showing how loans move between risk grades or buckets month over month, and non-performing loan (NPL) ratio trended over time."

# Evaluation:
This strategy produced a genuinely comprehensive, well-organized answer without any prompting toward Wildcat Capital's specific context. It correctly covered the major categories a real portfolio dashboard needs (concentration risk, reserves, originations, covenants) and used real industry terminology (ACL/CECL, migration analysis) unprompted. What's missing is any anchoring to our portfolio — the response is written generically for "a loan portfolio," with no reference to Wildcat's five loan purposes or four status categories, so it reads more like a textbook answer than something tailored for a specific audience or company. It's also somewhat exhaustive rather than prioritized — for an actual committee presentation, some sections (like stress testing) would need to be cut or deprioritized depending on the audience's time.

# Strategy 2: Role-assigned

# Complete prompt sent:
"You are a senior BI analyst at Wildcat Capital, a consumer lending company, presenting to a portfolio committee of senior executives who need to make quarterly decisions about the loan book. What should a BI dashboard for a loan portfolio committee include, and why?"

# First 150 words of Claude's response:
"This is a conversational, advisory question — no files or research needed, just domain expertise. Here's how I'd think about it as a BI analyst building for a Wildcat Capital portfolio committee. A loan portfolio committee's job is to decide whether to tighten or loosen underwriting, adjust pricing, shift capital across products or channels, and set aside the right reserves — all on a quarterly cadence. The dashboard needs to answer "is the book getting healthier or riskier, and where specifically" fast enough that the discussion moves to decisions rather than data-hunting. A few things earn their place for that reason: Portfolio composition and growth comes first — outstanding balances and origination volume by product, vintage, channel, and credit tier, with quarter-over-quarter and year-over-year trends. Committees need to see where growth is concentrated before they can judge whether it's the right kind of growth."

# Evaluation:
Assigning a role and audience noticeably changed the framing: the response opens by naming Wildcat Capital directly and grounds every section in what a committee is trying to decide, not just what data exists — for example, tying underwriting metrics explicitly to "did losses rise because underwriting already tightened, and is it working yet." It also introduced vintage-based loss curves as the single most-referenced chart in a real review, a level of practical, insider framing the zero-shot version didn't offer. The trade-off is length and density — this response reads more like a senior analyst's mental model than a clean deliverable, and it still doesn't reference Wildcat's actual five loan purposes or four status categories by name, so the "Wildcat Capital" framing is somewhat surface-level rather than fully grounded in the real dataset.

# Strategy 3: Few-shot

# Complete prompt sent:
"Here's an example of the format I'd like for your answer — a short intro sentence, followed by a numbered list where each item has a bolded label and a 1-2 sentence explanation:
Example:
 A good project retro covers a few key areas:
What went well — the wins worth repeating next time.
What didn't work — friction points or mistakes to avoid.
Now, using that same format: What should a BI dashboard for a loan portfolio committee include, and why?"

# First 150 words of Claude's response:
"A loan portfolio committee dashboard needs to answer three questions at a glance: how healthy is the book, where is risk concentrated, and what's changing. Here's what to include: 1. Portfolio composition and growth — total outstanding balance, number of loans, and growth trends by segment (product type, geography, vintage). This gives the committee the size and shape of the book before drilling into risk. 2. Delinquency and default rates — 30/60/90+ day delinquency buckets, current default rate, and trend lines over time. This is the earliest warning signal for credit quality deterioration. 3. Risk concentration — exposure by borrower, industry, geography, and credit grade, ideally with limits or thresholds overlaid. Concentration risk is what turns a manageable loss into a systemic problem, so the committee needs to see it clearly."
(That's 150 words.)

# Evaluation:
The few-shot example worked exactly as intended on format: Claude matched the bolded-label-plus-explanation structure precisely, including the short intro sentence before the list, with no deviation. The content itself covers similar ground to the zero-shot and role-assigned versions (delinquency, concentration, reserves, vintage performance) but is noticeably more scannable and consistent in length per item, which is genuinely useful for something a committee would actually read. The trade-off is that showing a format example used up prompt space without adding any business context, so this response is the least "tailored" of the three — it doesn't reference Wildcat Capital by name or reason about the audience's decision-making needs the way the role-assigned version did. It optimized structure at the expense of the depth and framing the other strategies offered.

# Conclusion:
Of the three strategies, the role-assigned version produced the most useful output for a BI analyst, because naming both the persona and the audience pushed Claude to frame every metric around what the committee needs to decide, not just what data exists — and it introduced practically-grounded details like vintage loss curve comparisons. The few-shot strategy produced the cleanest, most consumable format, which matters for something a committee will actually skim, but it didn't add business context beyond what zero-shot already provided. Zero-shot was comprehensive and accurate but the most generic — useful as a checklist, less useful as something ready to present. Overall, for real BI work, role-assignment mattered more for content quality, while few-shot mattered more for presentation quality, suggesting the two could be combined for the best result. 

# Fact-Check:
Claim checked: All three strategies referenced "Allowance for Credit Losses (ACL/CECL)" as a real accounting framework a portfolio committee dashboard should tie back to.
Verification: Confirmed accurate. CECL (Current Expected Credit Losses) is a real FASB accounting standard that requires companies to estimate expected losses over the life of a financial asset rather than waiting until a loss is probable, replacing the older incurred-loss model. It became effective for private companies for fiscal years beginning after December 15, 2022, so it's a current, active requirement for lenders like Wildcat Capital, not an outdated or theoretical concept. CliftonLarsonAllen
Takeaway: Claude's claim held up — it wasn't hallucinated or outdated. This is a good example of why fact-checking still matters even for reasonable-sounding claims: CECL/ACL is a common term Claude clearly has strong grounding in, but a BI analyst shouldn't assume that just because a claim sounds technically fluent, since the assignment's whole point is not to take AI-generated specifics on faith without checking a primary source.
