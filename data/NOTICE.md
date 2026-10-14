# Source attribution

## Existing Firewall1 application dataset

Firewall1 source: the dataset accompanying “On the Use of Max-SAT and PDDL in RBAC Maintenance”, https://onlinerbacfixing.github.io/cybersecurity2019/. The source page states CC BY 4.0: https://creativecommons.org/licenses/by/4.0/.

The source matrix at `raw/firewall1_UPA.txt` is unchanged. Its mechanical CSV conversion records each original 1 as one grant. U/P IDs are positional row/column labels, not invented identities or business permissions. The manifest records raw and derived SHA-256 hashes. This published variant contains 31,919 grants; the often-cited original Firewall1 has 31,951. No fabricated edge is added to match the latter.

## Five independent benchmark matrices

Americas Small, APJ, Healthcare, Domino and Firewall2 source files and direct links are listed in `test_sets/README.md`. The benchmark repository identifies the matrices as HP Labs real-world role-mining data and cites the SACMAT 2008 study. The project retains those two-column source matrices; the six extra CSV columns in the demo files are computed statistics, as defined in the manifest. The mirror repository does not state a separate dataset license, so review its terms before redistributing these files outside this project.

No Amazon history data or evaluation is part of this project.
