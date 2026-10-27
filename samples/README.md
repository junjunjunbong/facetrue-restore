# Sample material and provenance

No family videos, photographs, model weights or generated results are included in this directory. Keep actual media under gitignored `data/` or another private local directory.

## Archival candidate inspected

- [Home Movies - Western U.S., New Mexico, Mexico, California, Colorado, Utah](https://commons.wikimedia.org/wiki/File:Home_Movies_-_Western_U.S.,_New_Mexico,_Mexico,_California,_Colorado,_Utah.webm), Wikimedia Commons.
- [Original Prelinger/Internet Archive item](https://archive.org/details/6380_HM_Western_U_S_New_Mexico_Mexico_California_Colorado_Utah_01_00_33_20).
- Date listed: 1940; author listed as unknown.
- Wikimedia lists 42m58s, 640×480 and a file-specific Creative Commons Public Domain Dedication from Prelinger. Its page records a 2021-04-27 license review of the Archive source.
- The same page notes limitations of the old public-domain dedication instrument outside the US. Keep the exact source/license record with any selected excerpt.

The Wikimedia page was checked on 2026-10-27. The Archive page was not retrievable through the research tool, so no independent claim is made about its current contents. A usable shot/timecode has not been selected or visually reviewed for this project.

This is an archival restoration candidate. **No independently verified matching portrait of a depicted person has been found.** Do not pair it with an arbitrary photo and label the photo as the same person. The source is also not a clean-HQ ground truth dataset.

Prelinger is a collection, not one universal license. Check the individual item's rights and source record before using a different item.

## Controlled identity test

For the identity demo, prefer a short clip and separately captured photograph of a person who has agreed to their use. Keep a wrong-person photo from a second permitted source for the control condition. The reference must not be a frame from the target clip.

Record the following locally for every selected asset:

| Field | Required content |
|---|---|
| Asset role | HQ clip, actual archival clip, correct reference, or wrong reference |
| Provenance | Exact source URL or owner/permission record |
| Rights | Exact license or permission scope, including demo publication |
| Identity pairing | Operator-confirmed pseudonym for the person and the independent reference |
| Excerpt | Start time, duration, frame rate, and any crop |
| Changes | Deinterlacing, resizing, synthetic degradation, and prompt settings |
| Integrity | Original file hash and run manifest |

When a clean clip is deliberately degraded for evaluation, the public video must visibly say **Synthetically degraded test clip**. Do not represent a controlled degradation test as untouched VHS source material.
