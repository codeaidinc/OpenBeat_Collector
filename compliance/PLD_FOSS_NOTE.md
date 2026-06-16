> 本書はリーガルチェック前のドラフト（標準構成）です。弁護士確認のうえ確定してください。
>
> (This document is a pre-legal-review draft / standard configuration. Confirm with counsel before finalizing.)

# PLD / FOSS Note (OpenBeat Collector)

Last updated: 2026-06-16

## 1. License and "AS IS" / no warranty

OpenBeat Collector is distributed under the **Apache License, Version 2.0**. As
stated in the License (and the repository `NOTICE`), the software is provided on
an **"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND**, either
express or implied, and the contributors **disclaim liability** to the maximum
extent permitted by applicable law (Apache-2.0 §7–8).

## 2. New EU Product Liability Directive (Directive (EU) 2024/2853)

The revised EU Product Liability Directive (PLD), in force from 8 December 2024
with **national transposition due by 9 December 2026**, expressly treats
**software (including AI systems) and software updates as "products"** that can
give rise to strict liability for defects.

**FOSS exemption.** The new PLD provides that **free and open-source software
developed or supplied outside the course of a commercial activity** is, in
principle, **outside the scope** of the Directive's strict-liability regime.
OpenBeat Collector is published as FOSS under Apache-2.0.

## 3. Caveat — "commercial activity" / funnel risk (FLAG FOR LEGAL REVIEW)

The FOSS exemption turns on whether the software is supplied **outside a
commercial activity**. The following factors could cause the exemption to be
**lost or narrowed**, and must be reviewed by counsel:

- The collector is positioned within a broader product strategy (an "open side"
  feeding a "closed layer"), and distribution may function as a **funnel toward
  paid offerings or commercial services** provided by the operator/brand. Where
  free distribution is integrated into a commercial offering, regulators/courts
  may treat it as supplied **in the course of a commercial activity**, removing
  the FOSS exemption.
- Bundling, branded OEM distribution (協会 / JASTJ / WFSJ), paid support, or
  monetised packs/marketplace features could each weigh toward "commercial."

**Action:** Have counsel assess, per market (EU / UK / Japan), whether the
distribution model keeps OpenBeat Collector within the FOSS exemption, and
whether any commercial-funnel elements trigger PLD (and UK CPA 1987) producer
liability. Document the conclusion before relying on the exemption.

## 4. Related regimes (for completeness; confirm with counsel)

- **UK**: Consumer Protection Act 1987 (CPA) — product liability; assess software
  treatment separately from the EU PLD.
- **Japan**: 製造物責任法 (PL Act) — traditionally limited to movable tangible
  goods; software-as-product treatment differs from the EU PLD. Confirm current
  position and any reform.

## 5. Responsibility division (recap)

- Provider (CODEAID LLC): platform safety, explainability, logs, incident
  response, security, reasonable QA.
- User: input accuracy, final decisions, professional advice, and lawful use of
  collected data.
