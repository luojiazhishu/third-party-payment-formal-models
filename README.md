# Third-Party Online Payments Formal Verification

This repository contains formal models and verification scripts for analyzing the security of third-party online payments. In total, six real-world payment protocols are modeled and analyzed in this project, as summarized in the table below.

## Publication

This repository is the artifact of the following papers:

> **When Authorization Loses Its Meaning: Breaking and Fixing Third-Party Online Payments**
> Accepted to appear at the *35th USENIX Security Symposium (USENIX Security 2026)*.

> **Formal Analysis and Fixing of Third-Party Online Payment Protocols**
> Extended journal version (under review). It replaces the countermeasure of the conference version, which relies on trust on first use, with *Sealed Checkout Code* (SCC).

| Payment Scenario | Alipay                                                       | PSP-B Pay                                                    |
| ---------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| **In App**       | **Model:** `alipay_app.spthy`<br>**Official Document:** [APP](https://opendocs.alipay.com/open/00dn73?pathHash=b91b9616) | **Model:** `psp_b_pay_app.spthy` |
| **Mobile Web**   | **Model:** `alipay_mobile_web.spthy`<br>**Official Document:** [Mobile Website](https://opendocs.alipay.com/open/203/105288?pathHash=f2308e24) | **Model:** `psp_b_pay_h5.spthy` |
| **QR Code**      | **Model:** `alipay_order_code.spthy`<br>**Official Document:** [Order Code](https://opendocs.alipay.com/open/05osux?pathHash=660a1801) | **Model:** `psp_b_pay_native.spthy` |

## Repository Structure

- `./models/` — Tamarin Prover formal models  
  1. `base` — Both MF ⇐⇒ MS and MF ⇐⇒ PS are insecure  
  2. `secure_ms_channel` — Only MF ⇐⇒ PS is insecure  
  3. `secure_ps_channel` — Only MF ⇐⇒ MS is insecure  
  4. `countermeasures` — Countermeasure formal models of the conference version  
  5. `scc` — Sealed Checkout Code (SCC), the countermeasure of the journal version, under the `base` assumption  
  6. `control_commit_point` — Control experiment: the six protocol models under the three channel assumptions, with the user's commit for `U_MS_Order_Injective_Agreement` moved to the receipt of the payment result, as in the SCC model  
- `./scripts/` — Scripts for model verification and attack-graph generation  
- `./results/` — Formal verification results produced by Tamarin Prover  

## Install Tamarin Prover

This project relies on **Tamarin Prover** for formal security protocol analysis. Please install Tamarin Prover by following the official installation guide:

> **Tamarin Prover Official Installation Guide:**  
> https://tamarin-prover.com/install.html

After installation, verify that Tamarin Prover is available in your environment:

```bash
tamarin-prover --version
```

If the installation is successful, you should see output similar to the following:
```bash
tamarin-prover 1.10.0, (C) David Basin, Cas Cremers, Jannik Dreier, Simon Meier, Ralf Sasse, Benedikt Schmidt, 2010-2023

This program comes with ABSOLUTELY NO WARRANTY. It is free software, and you
are welcome to redistribute it according to its LICENSE, see
'https://github.com/tamarin-prover/tamarin-prover/blob/master/LICENSE'.

maude tool: 'maude'
 checking version: 3.1. OK.
 checking installation: OK.
Generated from:
Tamarin version 1.10.0
Maude version 3.1
Git revision: cb62c305f8c8b8c1e664152aa33c95b7b8d5ef32, branch: master
Compiled at: 2024-10-30 11:11:02.432289291 UTC
```

## Model Verification
The verification process involves the following steps:

```bash
# Install dependencies
apt install make 

# Run verification
make all
```
## Results
Formal verification results are stored under the `./results` directory. You can inspect each protocol’s outcome via the `result.json` file in the corresponding subfolder.

To view graphs, run Tamarin in **interactive mode** on a specific results subfolder, e.g.:

```bash
tamarin-prover interactive --derivcheck-timeout=0 ./results/base
```

### SCC and control experiment

- `results/scc/` — All five security properties of SCC (`PS_MS_Order_Injective_Agreement`, `U_MS_Order_Injective_Agreement`, `MS_PS_Response_Injective_Agreement`, `U_PS_Response_Injective_Agreement`, `No_Payment_Without_Password_Input`) are verified under the `base` assumption, in which both external channels are insecure.
- `results/control_commit_point/` — `U_MS_Order_Injective_Agreement` remains falsified in all 18 models, so moving the commit point does not by itself make the property hold.

These two folders contain the result summaries (`result.json`, `result.csv`) produced by Tamarin 1.10.0. To reproduce the proofs and traces, run `make all`.
