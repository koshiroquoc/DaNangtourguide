# Manual verification queue

`verification_queue_v1.csv` is a 200-place work queue, balanced as:

- 80 food/drink records
- 50 sights/experiences
- 70 stays

The score combines missing high-impact fields, a high-confidence attributable
source match, and fields rejected for staleness. It is not a popularity,
quality, or commercial ranking.

For each reviewed fact, retain at least:

- place `id` and field name;
- normalized value and original source value;
- exact source URL;
- source/update or observation date;
- verification date and reviewer identity/method;
- source license or usage basis.

Do not mark a place manually verified merely because a webpage loads. Prices
should come from a dated menu or booking result; opening hours should come from
the venue or another current attributable source. Phone calls or in-person
checks should record the date and method, without storing personal data.

Generated text is never an acceptable source for a factual field.
