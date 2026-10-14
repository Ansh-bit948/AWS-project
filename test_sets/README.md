# Real role-mining datasets

This folder contains five distinct, published user–permission access matrices: **Americas Small, APJ, Healthcare, Domino, and Firewall2**. They are separate matrices representing different systems/domains in the HP Labs benchmark family—not five time slices of one dataset. The original study describes the Cisco firewall, U.S. Veterans Administration healthcare, Lotus Domino, and firewall-monitoring sources and reports matrix dimensions. See [the HP Labs report](https://shiftleft.com/mirrors/www.hpl.hp.com/techreports/2008/HPL-2008-33.html), [the benchmark-data repository](https://github.com/carblu/rolemining/tree/main/datasets), and [a later paper reporting the benchmark dimensions and provenance](https://www.mdpi.com/2073-8994/16/8/1008).

## Files and sizes

| CSV | Users | Permissions | Assignments | Source file |
| --- | ---: | ---: | ---: | --- |
| `americas_small.csv` | 3,477 | 1,587 | 105,205 | [Original matrix](https://raw.githubusercontent.com/carblu/rolemining/main/datasets/americas_small.txt) |
| `apj.csv` | 2,044 | 1,164 | 6,841 | [Original matrix](https://raw.githubusercontent.com/carblu/rolemining/main/datasets/apj.txt) |
| `healthcare.csv` | 46 | 46 | 1,486 | [Original matrix](https://raw.githubusercontent.com/carblu/rolemining/main/datasets/hc.txt) |
| `domino.csv` | 79 | 231 | 730 | [Original matrix](https://raw.githubusercontent.com/carblu/rolemining/main/datasets/domino.txt) |
| `firewall2.csv` | 325 | 590 | 36,428 | [Original matrix](https://raw.githubusercontent.com/carblu/rolemining/main/datasets/fire2.txt) |

Every CSV has eight columns. `user_id` and `permission_id` are the original source identifiers. The other six columns are **derived, deterministic graph statistics**, calculated only from the assignments in that same matrix. They are useful for user profiling, permission prevalence, unusual-access detection, and role discovery; they are not claimed to be fields captured by the original organizations. The raw two-column `.source.txt` files are retained so the derived values can be independently reproduced.

The benchmark provides static grants, not event histories, HR profiles, approval timestamps, or successful/denied access attempts. It therefore supports role discovery, permission optimization, and structural risk analysis; it cannot by itself substantiate time-based behavior, approval latency, or reinforcement-learning outcomes. Identifiers are anonymized/ordinal and have no employee names or business meaning.

## Rebuild and provenance

Run `python scripts/build_test_sets.py` to rebuild the CSVs and `manifest.json` from the retained source files. The builder checks the unique user, permission, and assignment counts against published benchmark counts and records each raw source SHA-256 in the manifest. The public source repo identifies these matrices as real datasets made available from HP Labs and cites the SACMAT 2008 report. The mirror's repository page does not state a separate dataset license; cite the HP Labs study and review the source repository terms before redistribution beyond this project. The five matrices are independent datasets within one benchmark family, not independent publishers.
