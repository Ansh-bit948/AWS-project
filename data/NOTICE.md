# Dataset attribution

The Firewall1 permission-to-user access-control matrix is from the dataset accompanying ?On the Use of Max-SAT and PDDL in RBAC Maintenance,? hosted at <https://onlinerbacfixing.github.io/cybersecurity2019/>. The dataset page states that the data are licensed under Creative Commons Attribution 4.0 International (CC BY 4.0): <https://creativecommons.org/licenses/by/4.0/>.

The untouched source matrix is `raw/firewall1_UPA.txt`. `processed/firewall1_upa.csv` is a mechanical conversion: each matrix row is treated as a user, each column as a permission, and each `1` becomes one grant. IDs (`U0001?`, `P0001?`) are positional labels assigned for this conversion; they do not identify real people, systems, or business permissions. No records or grants are synthesized. See `processed/firewall1_manifest.json` for hashes, dimensions, and validation counts.
