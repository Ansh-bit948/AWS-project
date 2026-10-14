# Research and novelty notes — updated 15 October 2026

The project combines sparse role discovery, policy-structure optimization, provenance-linked review, versioned application authorization, conditional AWS transactions, and a model trained only from actual administrator feedback.

The benchmark sample set contains five distinct real-world matrices from the HP Labs role-mining collection. Its source IDs are anonymous/ordinal. No business-role attributes or approval outcomes are supplied. Additional CSV fields are deterministic structural statistics, not original source attributes.

Role mining, WSC, set-cover/factoring heuristics and Q-learning have substantial prior work. Combining these techniques in an application does not establish novelty. Patentability needs a specific technical contribution and an appropriate prior-art and legal review.

Primary references:
- HP Labs, “Fast Exact and Heuristic Methods for Role Minimization Problems”: https://shiftleft.com/mirrors/www.hpl.hp.com/techreports/2008/HPL-2008-33.html
- Public benchmark matrix repository: https://github.com/carblu/rolemining/tree/main/datasets
- Published dimensions and source-domain summary: https://www.mdpi.com/2073-8994/16/8/1008
- Original role-minimization work: https://geometry.stanford.edu/lgl_2024/papers/ehmrst-fehmrmp-08/ehmrst-fehmrmp-08.pdf
- DynamoDB transaction semantics: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis.html

A future research hypothesis is whether coverage-preserving factoring and provenance-linked human feedback can reduce measured policy-review work while keeping false-denial rates low. Testing that requires a genuine ERP feed, administrator labels, time-aware evaluation and external algorithm baselines.

No claim of patentability, a formal Zelkova proof, or a new reinforcement-learning algorithm is made. The current project is a reproducible engineering/research implementation.
