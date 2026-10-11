# Source attribution

Firewall1 source: the dataset accompanying “On the Use of Max-SAT and PDDL in RBAC Maintenance”, https://onlinerbacfixing.github.io/cybersecurity2019/. The source page states CC BY 4.0: https://creativecommons.org/licenses/by/4.0/.

The source matrix at `raw/firewall1_UPA.txt` is unchanged. Its mechanical CSV conversion records each original 1 as one grant. U/P IDs are positional row/column labels, not invented identities or business permissions. The manifest records raw and derived SHA-256 hashes. This published variant contains 31,919 grants; the often-cited original Firewall1 has 31,951. No fabricated edge is added to match the latter.

Amazon Access Samples: Ken Montanez (2011), UCI Machine Learning Repository, DOI https://doi.org/10.24432/C5JW2K; source https://archive.ics.uci.edu/dataset/216/amazon+access+samples. UCI states CC BY 4.0.

`scripts/prepare_amazon_history.py` downloads the unchanged official archive and extracts only `amzn-anon-access-samples-history-2.0.csv`. It preserves source user/target IDs and observed actions/timestamps, records exclusions and hashes, and writes separate derived analytics. Raw Amazon files are ignored by Git; attribution and computed evaluations are included. The wide access snapshot is not expanded or claimed as processed. The Amazon and Firewall1 populations are never joined.
