# Research and novelty notes — 11 October 2026

The technical artifact combines sparse exact role reconstruction, greedy structural-cost reduction, immutable source provenance, versioned application authorization, conditional AWS transactions, and models trained on actual observed feedback/outcomes.

Role mining, WSC, set-cover/factoring heuristics and Q-learning already have extensive prior work. Implementing these together does not establish novelty. The Phase-I report's proposed semantic department roles cannot be supported by opaque ACL labels. A source with genuine attributes would be needed for that experiment.

Primary references:
- Published Firewall1 variant and research context: https://onlinerbacfixing.github.io/cybersecurity2019/
- Original role graph benchmark study: https://geometry.stanford.edu/lgl_2024/papers/ehmrst-fehmrmp-08/ehmrst-fehmrmp-08.pdf
- Stony Brook benchmark collection description: https://www3.cs.stonybrook.edu/~liu/papers/RoleMiningData-LPOP20.pdf
- UCI Amazon enterprise access source: https://archive.ics.uci.edu/dataset/216/amazon+access+samples
- DynamoDB transaction semantics: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis.html

A future research hypothesis is whether coverage-preserving factoring and provenance-linked human feedback can reduce measured policy-review work while keeping false-denial rates low. Testing that requires a genuine ERP feed, administrator labels, time-aware evaluation and an external algorithm baseline.

No claim of patentability, legal eligibility, a formal SMT/Zelkova proof, or a new RL algorithm is made. The present project is a reproducible engineering/research implementation. Any IP decision needs a specific technical contribution and an appropriate prior-art review before filing or claiming novelty.
