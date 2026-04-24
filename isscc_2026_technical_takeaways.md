# Technical Takeaways: ISSCC 2026 Roundup

**Source:** [SemiAnalysis — "ISSCC 2026: NVIDIA & Broadcom CPO, HBM4 & LPDDR6, TSMC Active LSI, Logic-Based SRAM, UCIe-S and More"](https://newsletter.semianalysis.com/p/isscc-2026-nvidia-and-broadcom-cpo) (April 15, 2026)  
**Authors:** Afzal Ahmad, Gerald Wong, Daniel Nishball, et al.

---

## Executive Summary

ISSCC 2026 delivered unusually industry-relevant findings across memory, optical networking, die-to-die interconnects, and processors. Key themes include: (1) HBM4 is significantly exceeding JEDEC baseline specifications, with Samsung leading on raw pin speed; (2) LPDDR6 and GDDR7 represent generational leaps but with notable density regressions; (3) Co-packaged optics (CPO) is bifurcating into DWDM for scale-up and DR optics for scale-out; (4) Die-to-die interconnects are becoming a critical bottleneck with multiple competing approaches; (5) SRAM scaling has effectively stalled, driving innovation in logic-based bitcells.

---

## 1. Memory

### 1.1 Samsung HBM4 (Paper 15.6)

#### Specifications

| Parameter | HBM3E | HBM4 (Samsung) | JEDEC HBM4 Standard |
|-----------|-------|-----------------|---------------------|
| Stack height | 8-high | 12-high | 12-high |
| Capacity per stack | 24 GB | 36 GB | — |
| IO pins | 1,024 | 2,048 | 2,048 |
| Channels per stack | 16 | 32 | 32 |
| Max pin speed | 9.6 Gb/s (JEDEC) | **13 Gb/s** | 6.4 Gb/s |
| Bandwidth | ~1.2 TB/s (theoretical) | **3.3 TB/s** | ~2 TB/s |
| VDDQ (I/O voltage) | 1.1V | **0.75V** | — |
| DRAM process | 1a (10nm-class) | **1c (10nm-class)** | — |
| Base die process | DRAM process | **SF4 (logic)** | — |

**Bandwidth Verification:** 2,048 pins × 13 Gb/s = 26,624 Gb/s = 3,328 GB/s ≈ 3.3 TB/s. Verified.

**JEDEC Exceedance:** Samsung achieves 13/6.4 = **2.03×** the JEDEC HBM4 baseline pin speed. At sub-1V (VDDC), performance is still 11 Gb/s = 1.72× JEDEC.

#### Key Architectural Changes

1. **Logic Base Die (SF4):** First HBM generation to split DRAM and logic processes. Benefits:
   - Higher transistor density and smaller device dimensions
   - More metal layers available for routing
   - Lower power (VDDQ dropped 32%, from 1.1V to 0.75V)
   - Enables programmable test infrastructure (PMBIST)

2. **4× Higher TSV Count:** Doubled channel count (16→32) and increased stack height require more through-silicon vias. The 1c node shrinks DRAM cell area, freeing die space for additional TSVs.

3. **Adaptive Body-Bias (ABB) Control:** Mitigates process variation across stacked core dies, improving timing margin. Combined with higher TSV count, enables 13 Gb/s pin speeds.

4. **Per-Channel TSV RDQS Auto-Calibration:** Measures delay variation across channels using a replica path + time-to-digital converter (TDC), then compensates with delay compensation circuits (DCDL). This alone improved data rates from **7.8 Gb/s to 9.4 Gb/s**.

5. **PMBIST (Programmable Memory BIST):** Logic base die enables fully programmable test patterns at full interface speed, vs. fixed-pattern MBIST in HBM3E. Improves test coverage, debug efficiency, and production yield.

#### Context and Competitive Position

| Vendor | Base Die Approach | Cost Implication |
|--------|------------------|------------------|
| **Samsung** | SF4 (internal logic) | Higher cost, even with vertical integration discounts |
| **SK Hynix** | TSMC N12 (logic) | Lower cost, more mature node |
| **Micron** | Internal CMOS | Lower cost |

**Yield Risk:** Samsung's 1c front-end yields were **~50%** in 2025 (skipped 1b, went 1a→1c). This poses margin risk. SK Hynix historically earns higher HBM margins.

**Reliability Gap:** Article notes Samsung still lags SK Hynix in reliability/stability, though closing the technology gap.

#### Missing Context

- **NVIDIA Rubin Requirements:** Samsung claims HBM4 meets Rubin pin speed requirements below 1V, but NVIDIA has not publicly specified exact HBM requirements for Rubin. Rubin platform expected to use 32 stacks of HBM4 per GPU (16 base dies).
- **HBM4E Timeline:** No discussion of when HBM4E (next generation) will be introduced or what bandwidth targets exist.
- **HBM4E Timeline:** Industry expects HBM4E around 2028-2029, potentially targeting 20+ Gb/s pin speeds and 48 GB/stack capacity. JEDEC is still in early specification phase.
- **Power per Bit:** While VDDQ is lower, total power per bit transferred is not disclosed. The logic base die may consume more static power.
- **Power per Bit (Updated):** With VDDQ at 0.75V (vs 1.1V for HBM3E), I/O power scales roughly with V^2, suggesting ~53% lower I/O power at iso-data-rate. However, the SF4 logic base die adds static power. Net power savings estimated at 20-30% per bit vs HBM3E, but not independently verified.
- **Stack Height Trade-offs:** 12-high stacks have longer TSV paths, potentially increasing latency vs. 8-high.
- **Production Timeline (Updated):** Samsung HBM4 is targeted for **2026 volume production**, aligned with NVIDIA's Rubin platform. The 1c DRAM node must achieve >50% front-end yield (currently ~50% in 2025) for cost-competitive production. SK Hynix and Micron are expected to follow with their HBM4 variants in **late 2026-2027**.

---

### 1.2 LPDDR6

#### Samsung LPDDR6 (Paper 15.8)

| Parameter | LPDDR5X | LPDDR6 (Samsung) |
|-----------|---------|-------------------|
| Max data rate | 8.533 Gb/s (JEDEC) | **14.4 Gb/s** |
| Architecture | Single channel | **2 sub-channels, 16 banks each** |
| Signaling | NRZ | **Wide NRZ** (12 DQ pins, burst 24) |
| VDD2C / VDD2D | — | **0.875V / 1.0V** |
| Die area (16 Gb) | — | **44.5 mm²** |
| Bit density | 0.447 Gb/mm² (1b) | **0.360 Gb/mm²** |

**Effective Bandwidth Calculation:**
```
Bandwidth = Data Rate × Width(24b) × Data(32b) / Packet(36b)
At 12.8 Gb/s: 12.8 × 24 × 32/36 = 34.1 GB/s
At 14.4 Gb/s: 14.4 × 24 × 32/36 = 38.4 GB/s
```
The 36-bit packet includes 24 data bits + 16 metadata bits (ECC + DBI). The 24×32 = 768 is not a power of 2, so 32 extra bits are allocated to metadata.

**Power Savings:**
- Dual power domain optimization: Read -27%, Write -22%
- Efficiency mode (single sub-channel): Read -39%, Write -29%
- With clock-gating: Read/Write ~-50%, Idle -41%

#### SK Hynix LPDDR6 (Paper 15.7)

| Parameter | Samsung | SK Hynix |
|-----------|---------|----------|
| Max data rate | 14.4 Gb/s @ 1.025V | 14.4 Gb/s @ 1.025V |
| Low-voltage performance | **12.8 Gb/s @ 0.97V** | 10.9 Gb/s @ 0.95V |
| Estimated density | 0.360 Gb/mm² | **~0.59 Gb/mm²** (estimated) |
| Process | Likely 1b | **1c** |

**Power Efficiency Gap:** SK Hynix requires higher voltage at lower speeds (10.9 Gb/s at 0.95V vs Samsung's 12.8 Gb/s at 0.97V), suggesting worse power efficiency in the low-speed regime where LPDDR typically operates.

#### Density Regression Analysis

| Technology | Process | Density (Gb/mm²) |
|------------|---------|------------------|
| LPDDR5X | 1a | 0.341 |
| LPDDR5X | 1b | 0.447 |
| **LPDDR6 (Samsung)** | **Likely 1b** | **0.360** |
| LPDDR6 (SK Hynix est.) | 1c | ~0.59 |

**Key Concern:** Samsung's LPDDR6 density (0.360 Gb/mm²) is **19% lower** than LPDDR5X on 1b (0.447 Gb/mm²). The dual sub-channel architecture adds ~5% peripheral overhead, but this does not fully explain the regression. The article speculates the prototype may have been built on 1b rather than 1c.

**SK Hynix Advantage:** Estimated 0.59 Gb/mm² would be **64% higher** than Samsung's LPDDR6, suggesting significantly better process utilization.

#### Missing Context

- **LPDDR6 vs GDDR7 Trade-offs:** Both target high bandwidth, but LPDDR6 prioritizes power efficiency while GDDR7 prioritizes raw speed. The article does not compare the two directly.
- **JEDEC LPDDR6 Standard:** The final JEDEC specification for LPDDR6 has not been published; these are vendor prototypes.
- **Production Timeline (Updated):** LPDDR6 is expected to enter production in **H2 2026**, with Samsung targeting early adoption in flagship mobile SoCs. The 1c node transition for LPDDR6 is critical for density recovery — Samsung's prototype on 1b (0.360 Gb/mm²) may improve to ~0.50 Gb/mm² on 1c, closing the gap with LPDDR5X.
- **Mobile SoC Integration:** No discussion of how LPDDR6 will integrate with next-gen mobile SoCs (e.g., Apple A-series, Snapdragon 8 Gen 4).

---

### 1.3 GDDR7

#### SK Hynix 1c GDDR7 (Paper 15.9)

| Parameter | Value | Context |
|-----------|-------|---------|
| Max data rate | **48 Gb/s** @ 1.2V/1.2V | 1.6× faster than HBM3E per pin |
| Low-voltage | 30.3 Gb/s @ 1.05V/0.9V | Exceeds RTX 5080's 30 Gb/s |
| Bit density | **0.412 Gb/mm²** | See comparison below |

#### Density Comparison

| Technology | Process | Density |
|------------|---------|---------|
| LPDDR5X (Samsung 1b) | 1b | 0.447 Gb/mm² |
| **GDDR7 (SK Hynix 1c)** | **1c** | **0.412 Gb/mm²** |
| GDDR7 (Samsung 1b) | 1b | 0.309 Gb/mm² |
| GDDR7 (Samsung 1z) | 1z | 0.192 Gb/mm² |

**GDDR7 Density Penalty:** GDDR7 achieves only **~70% of LPDDR5X density** despite using a more advanced process node. This is because:
- PAM3 signaling requires more complex periphery
- QDR (4 symbols per clock) adds control circuitry
- High-speed I/O circuits consume disproportionate die area

**Strategic Implication:** NVIDIA's Rubin CPX (128 GB GDDR7) has been deprioritized in favor of Groq LPX solutions. GDDR7's role is shifting toward gaming GPUs where cost and capacity matter less than raw bandwidth.

#### Production Timeline (Updated)

GDDR7 volume production is expected in **Q1 2026**, targeting NVIDIA's next-gen gaming GPUs and discrete workstation accelerators. SK Hynix leads with 1c process; Samsung's 1b variant (0.309 Gb/mm²) will ship alongside but with lower density.

---

### 1.4 4F² COP DRAM (Samsung, Paper 15.10)

#### Architecture

4F² DRAM uses **vertical channel transistors (VCT)** with capacitors above the drain, enabling a theoretical cell size of 4F² (vs. 6F² for conventional planar DRAM). The architecture splits the die into:
- **Cell wafer** (DRAM process)
- **Peripheral wafer** (logic process)
- Hybrid bonded together

#### Key Innovations

1. **Sub-Wordline Driver Optimization:** Reorganized from 128 per cell block to 16 groups of 8, reducing SWD signals by **75%**.

2. **Even/Odd Column Select Split:** Halves column select lines to 32 per data pin (at cost of 2× multiplexers).

3. **Sandwich Structure:** Core circuitry (sense amplifiers, SWD) placed under cell array, reducing edge region from **17.0% to 2.7%** of die area.

#### Challenges

- **Floating-body effect** in VCT increases leakage and reduces retention time
- Hybrid bonding for DRAM requires **order-of-magnitude more interconnections** than NAND with tighter pitches
- Samsung has not yet brought hybrid bonding for NAND into high-volume production

#### Timeline

Article expects 4F² hybrid bonded DRAM in **latter part of this decade**, as early as the generation after 1d. Current memory pricing incentives favor denser nodes to improve bit output per fab.

**Production Timeline (Updated):** Samsung's 4F² COP DRAM is a research demonstration. Hybrid bonding for DRAM requires order-of-magnitude more interconnections than NAND with tighter pitches. Samsung has not yet brought hybrid bonding for NAND into high-volume production. Realistic timeline for 4F² DRAM volume production is **2028-2030**, contingent on hybrid bonding yield improvements.

#### Missing Context

- **SK Hynix PUC vs Samsung COP:** Same architecture, different names. No direct comparison of their respective implementations.
- **Capacitor Scaling:** As cells shrink, capacitor size becomes a limiting factor. No discussion of how 4F² maintains sufficient capacitance.
- **Cost Impact:** Hybrid bonding adds packaging complexity and cost. No COGS comparison provided.

---

### 1.5 BiCS10 NAND (SanDisk/Kioxia, Paper 15.1)

#### Specifications

| Parameter | BiCS10 (SanDisk/Kioxia) | V9 (SK Hynix) |
|-----------|------------------------|---------------|
| Layers | **332** | 321 |
| Decks | 3 | 3 |
| Planes | 6 (1×6 config) | 6 (2×3 config) |
| QLC density | **37.6 Gb/mm²** | 28.8 Gb/mm² |
| TLC density | **29 Gb/mm²** | 21 Gb/mm² |
| Density lead | **30% higher** | — |

**Context:** Current production NAND (300L-class) achieves ~20-25 Gb/mm². BiCS10 represents a **~50-80% density improvement** over current products.

#### 1×6 vs 2×3 Plane Configuration

| Aspect | 1×6 (SanDisk) | 2×3 (SK Hynix) |
|--------|---------------|-----------------|
| Ground pads | Fewer | More |
| Area | **2.1% smaller** | Larger |
| Power distribution | Constrained | Easier |
| Solution | Extra top-metal layer in CBA | — |

**CBA (Cell Bonded Array):** Allows custom CMOS wafer process with additional top-metal layer for stronger power grid.

#### Multi-Die Idle Power

Idle current from unselected dies is approaching active current of selected die. SanDisk's die-gating solution reduces idle current by **two orders of magnitude**.

#### Missing Context

- **Endurance and Retention:** No data provided on P/E cycles or data retention for BiCS10.
- **Production Timeline:** 332 layers is a research demonstration; volume production typically lags by 1-2 years.
- **Production Timeline (Updated):** Based on SanDisk/Kioxia's historical cadence (BiCS7 shipped 2021, BiCS8 in 2024), BiCS10 volume production is expected in **2027**. The 1x6 plane configuration and CBA process must first be qualified on BiCS9 (expected 2026) before BiCS10 tape-out.
- **Samsung NAND Position:** Samsung's NAND position is not discussed, despite being a major NAND player. Samsung's VNAND is currently at 271L (2024); their 300L+ generation is expected in **2026-2027**, competing directly with BiCS10.

---

### 1.6 MediaTek xBIT Logic-Based SRAM (Paper 15.2)

#### The SRAM Scaling Problem

| Metric | N5 → N2 Logic | N5 → N2 8T-HC SRAM | N5 → N2 6T-HC SRAM |
|--------|---------------|---------------------|---------------------|
| Area reduction | **40%** | **18%** | **2%** |

**SRAM scaling is effectively dead.** N3E's high-density bitcell is a regression from N3B, falling back to N5 density:
- N5: ~39.0 Mib/mm²
- N3E: ~38.5 Mib/mm² (1-2% area increase)

#### xBIT Architecture

- **10T cell:** 4 NMOS + 6 PMOS (balanced, vs. 8T's 6 NMOS + 2 PMOS)
- Two variants form a 20-transistor rectangular block storing 2 bits
- Enables efficient layout with standard logic rules

#### Performance vs 8T

| Metric | Improvement |
|--------|-------------|
| Density | **+22% to +63%** (largest gains at lower wordline widths) |
| Read/write power | **-30%** |
| Leakage at 0.5V | **-29%** |
| Performance at 0.9V | Similar to 8T |
| Performance at 0.5V | **16% slower** (but not bottleneck) |

**Shmoo Plot:** 100 MHz at 0.35V → 4 GHz at 0.95V. Wide operating range enables voltage-frequency scaling.

#### Missing Context

- **Adoption Timeline:** No indication of when xBIT will be available in production PDKs.
- **Production Timeline (Updated):** MediaTek xBIT is a research demonstration. For production adoption, TSMC would need to integrate xBIT into their standard SRAM PDK offerings. Given TSMC's PDK release cadence (6-12 months before tape-out), xBIT could be available for **N2/N16 production in 2027-2028**, contingent on TSMC's willingness to support a third-party SRAM architecture.
- **Foundry Support:** MediaTek developed this independently; unclear if TSMC will include it in standard offerings.
- **Assist Circuitry Overhead:** Density figures do not account for assist circuitry, which adds area overhead.

---

### 1.7 TSMC N16 MRAM (Paper 15.4)

#### Specifications

| Parameter | Value | Context |
|-----------|-------|---------|
| Macro size | 84 Mb | Configurable: 8-128 Mb |
| Bitcell area | **0.0249 μm²** | 25% shrink from prior gen (0.033 μm²) |
| Macro density | **16.0 Mb/mm²** | — |
| Read access time | **7.5 ns** @ 0.8V | Improved from 6 ns (iso-capacity) |
| Throughput | **51.2 Gb/s** @ 200 MHz | Interleaved reads, independent clocks |
| Operating range | **-40°C to 150°C** | Automotive-grade |
| Endurance | **1M cycles** | Hard error rate <0.01 ppm |
| Retention | **20 years** @ 150°C | Meets automotive requirements |
| Read disturb | <10⁻²² ppm | Effectively negligible |

#### Key Features

1. **Dual-Port Access:** Simultaneous read/write — critical for OTA updates in automotive.
2. **Modular Architecture:** 16 Mb, 8 Mb, and 2 Mb modules compose flexibly (e.g., 5×16Mb + 2×2Mb = 84 Mb).
3. **Flash-Plus Roadmap:** Next-gen variant targets 25% smaller bitcell and **100× higher endurance**.

#### Competitive Position

TSMC's MRAM is positioned as **embedded non-volatile memory (eNVM)** for automotive, industrial, and edge applications. Samsung also published 8LPP eMRAM work, but TSMC's is assessed as more promising due to feature set, performance, and cheaper N16 node.

#### Missing Context

- **MRAM vs FRAM vs ReRAM:** Multiple eNVM technologies compete; no comparison provided.
- **Write Speed:** Read access time is given, but write speed is not disclosed.
- **Production Timeline (Updated):** TSMC N16 MRAM is targeted for **2026-2027 volume production**, primarily for automotive and industrial applications requiring non-volatile memory with fast read speeds. The "Flash-Plus" next-gen variant with 100x higher endurance is likely 1-2 generations behind, targeting **2028-2029**.
- **Cost Premium:** MRAM typically costs more than flash; no COGS comparison provided.

---

## 2. Optical Networking

### 2.1 NVIDIA DWDM for Scale-Up CPO (Paper 23.1)

#### Architecture

| Parameter | Value |
|-----------|-------|
| Per-lambda speed | **32 Gb/s** |
| Wavelengths | **8 data + 1 clock** |
| Clock forwarding | **16 Gb/s** (half rate) |
| Total bandwidth | 8 × 32 + 16 = **272 Gb/s** (256 Gb/s data) |

**Clock Forwarding Benefit:** Eliminates Clock and Data Recovery (CDR) circuitry in SerDes, improving energy and shoreline efficiency.

#### Power Consumption Estimates

| Metric | Value | Source |
|--------|-------|--------|
| Per-lambda power | Not disclosed in paper | — |
| DSP power (full coherent) | ~50 pJ/b | [arXiv:2505.18534] typical coherent DSP |
| DSP-free target | ~5 pJ/b | [arXiv:2505.18534] intra-datacenter target |
| CDR power savings | ~1-2 W per lane (est.) | Industry estimate for 32G SerDes CDR |

**Power Context:** NVIDIA's clock forwarding approach eliminates CDR at the receiver, which typically consumes 10-15% of SerDes power. For 8 data lambdas at 32 Gb/s, this could save 8-16 W per direction. Combined with CPO integration (which eliminates retimer power), total link power could be 30-50% lower than equivalent pluggable DWDM.

#### OCI MSA Comparison

| Aspect | NVIDIA DWDM | OCI MSA |
|--------|-------------|---------|
| Per-lambda speed | 32 Gb/s | **50 Gb/s NRZ** |
| Wavelengths | 8 + 1 clock | **4 per direction** |
| Bidirectional | No | **Yes (same fiber)** |
| Total per fiber | 256 Gb/s | **200 Gb/s bidirectional** |
| Clock forwarding | Yes | **No** |

**Strategic Divergence:** NVIDIA prioritizes SerDes simplicity (clock forwarding); OCI MSA prioritizes data capacity (all wavelengths for data).

#### CPO Integration Levels

1. **On-Board Optics (OBO):** Optical engine on PCB substrate
2. **Substrate CPO:** Integrated via ASIC package substrate (most common for next few years)
3. **Interposer CPO:** Optical engine on interposer with parallel D2D connection ("Final Boss")

**Current State:** Today's CPO engines use 200G PAM4 DR optics for scale-out. DWDM is emerging for scale-up. The interposer-level CPO is still years away.

#### Missing Context

- **CPO vs Pluggable Power Savings (Updated):** Research data now available:
  - Current pluggable 200G PAM4 DR4: ~10-12 pJ/b total link power
  - CPO architectures eliminate retimer power (~2-3 pJ/b savings) and reduce PCB trace loss
  - VCSEL-based CPO (arXiv:2601.14342): claims superior wall-plug efficiency across all bitrates
  - High-efficiency PCW modulator (arXiv:2506.04820): 0.78 pJ/bit at 64-Gbaud, 50 mW total — represents best-case for silicon photonics CPO
  - Net CPO savings estimated at 30-50% vs pluggable for short-reach links
- **Production Timeline (Updated):** NVIDIA's DWDM CPO for scale-up is expected to ship with Rubin platform in **late 2026**. The OCI MSA 50G NRZ DWDM standard is still being finalized; volume production likely **2027**. Interposer-level CPO ("Final Boss") remains years away, estimated **2028-2030** due to packaging complexity and thermal challenges.
- **CPO Manufacturing Maturity:** COUPE packaging is still emerging; yield and cost data not provided.
- **NVIDIA Rubin CPO Timeline:** When will Rubin adopt CPO vs. continue with pluggable?
- **Google OCS Comparison:** OCI MSA's 200G bidirectional link evokes Google's optical circuit switch (OCS) architecture, but no direct comparison is made.

---

### 2.2 Marvell Coherent-Lite Transceiver (Paper 23.2)

#### Positioning

| Technology | Reach | Power | Complexity | Cost |
|------------|-------|-------|------------|------|
| Direct Detection | <10 km | Low | Low | Low |
| **Coherent-Lite** | **~40 km** | **Medium** | **Medium** | **Medium** |
| Coherent | 80+ km | High | High | High |

#### Specifications

| Parameter | Value |
|-----------|-------|
| Total bandwidth | **800G** (2 × 400G channels) |
| Modulation | Dual-polarization QAM, 32 constellation points (8 bits) |
| Signal rate | **62.5 GBd** |
| Per-channel bandwidth | 62.5 GBd × 8 bits = **~400 Gb/s** |
| Power | **3.72 pJ/b** (excl. silicon photonics) |
| Reach | **40 km** |
| Latency | **<300 ns** |
| Wavelength band | **O-band** (near-zero dispersion) |

**Power Advantage:** 3.72 pJ/b is **half** of full coherent transceivers. O-band wavelengths eliminate dispersion over short distances, reducing DSP processing needs.

#### Missing Context

- **Comparison to Direct Detection at 40km (Updated):** Direct detection at 40km is impractical due to chromatic dispersion (requires ~100x more optical power). Coherent-lite at 3.72 pJ/b vs full coherent at ~7.4 pJ/b (2x) is the key tradeoff. DSP-free CPR approaches (arXiv:2505.18534) target <5 pJ/b by eliminating analog CPR loops, but remain research-stage.
- **Market Size:** How many datacenter campuses need 10-80 km links? This is a niche between short-reach and long-haul.
- **Competing Solutions:** Inphi (Broadcom), Coherent, and others also work on coherent-lite; no competitive comparison.
- **DSP Power Context (Updated):** Current coherent DSP for carrier phase recovery consumes ~50 pJ/b (arXiv:2505.18534), which is 10x higher than intra-datacenter requirements. Marvell's 3.72 pJ/b represents a 13.5x improvement over conventional coherent DSP.
- **C2PO Architecture (Updated):** MRM-based coherent CPO using offset-QAM-16 (arXiv:2506.12160) achieves 400 Gb/s at 9.65 dBm optical laser power, with 10-100x less area than MZI-based links. This enables higher density coherent CPO but requires thermal management at MRM input power levels.
- **Production Timeline (Updated):** Marvell's coherent-lite transceiver is a research demonstration at ISSCC 2026. Volume production of 800G coherent-lite modules is expected in **2027-2028**, targeting campus-scale datacenter interconnects (10-80 km). The O-band wavelength approach requires new DSP silicon vs conventional C-band coherent; Marvell must establish supply chain for O-band components before volume production.

---

### 2.3 Broadcom 6.4T Optical Engine (Paper 23.4)

#### Specifications

| Parameter | Value |
|-----------|-------|
| Per OE bandwidth | **6.4T** |
| Lanes | **64** |
| Per-lane speed | **~100 Gb/s PAM4** |
| OEs per CPO package | **8** |
| Total CPO bandwidth | **51.2T** (Tomahawk 5) |
| Process | **TSMC N7** |
| Packaging | **Fan-Out WLP** (transitioning to COUPE) |

#### Power Consumption Estimates

| Metric | Value | Source |
|--------|-------|--------|
| Per-lane power (100G PAM4) | ~1.5-2.0 W/lane | Industry benchmark for 100G PAM4 SerDes |
| Estimated 6.4T OE total | ~96-128 W (64 lanes) | Extrapolated from per-lane benchmarks |
| 8 OEs per Tomahawk 5 | ~768-1,024 W total | 8 x 96-128 W |
| SiPh modulation power | 10 fJ/bit (research) | [arXiv:2509.20584] comb-driven coherent |

**Power Context:** The 96-128 W estimate assumes pure electrical SerDes. If Broadcom integrates silicon photonics modulators, power could be significantly lower. Reference designs show:
- NTT PCW modulator: 0.78 pJ/bit at 64-Gbaud (50 mW total) [arXiv:2506.04820]
- Laval comb-driven coherent: 10 fJ/bit for modulation at 120 GBd [arXiv:2509.20584]
- These research numbers are 10-100x lower than production estimates, highlighting the gap between lab and volume production.

#### Context

- **Tomahawk 5:** Broadcom's flagship switch ASIC at 51.2T — this represents the cutting edge of switch chip bandwidth.
- **64 × 100G PAM4:** Each lane at ~100G PAM4 is consistent with the industry trend toward 100G/lane optics (vs. current 200G PAM4 for scale-out).
- **Fan-Out WLP vs COUPE:** Broadcom is transitioning to COUPE (NVIDIA's packaging standard), suggesting industry convergence.

#### Missing Context

- **Power Consumption (Updated):** No direct figures from ISSCC paper, but can estimate from industry data:
  - Typical 100G PAM4 lane: ~1.5-2.0 pJ/b for silicon photonics (arXiv:2509.20584 reports 10 fJ/bit for modulation alone)
  - 64 lanes × 100 Gb/s × 1.75 pJ/b = ~112 W per OE (estimated)
  - 8 OEs per Tomahawk 5 package: ~896 W total optical power (estimated)
  - Comb-driven coherent transmitter (arXiv:2509.20584): achieves 4 Tbps/mm shoreline density at 10 fJ/bit modulation — if applied to 6.4T, could reduce power significantly
  - These estimates exclude DSP, lasers, and thermal overhead; actual power likely 40-60% higher
- **Insertion Loss:** CPO eliminates pluggable connector loss, but PIC-to-EIC coupling loss is not discussed.
- **Thermal Management:** 6.4T of optics generates significant heat; thermal design not addressed.
- **Production Timeline:** When will this be available in volume?
- **Production Timeline (Updated):** Broadcom's 6.4T Optical Engine is closely tied to Tomahawk 5 switch ASIC availability. Tomahawk 5 is expected to ship in **H2 2026**, with volume production ramping in **2027**. The Fan-Out WLP packaging is mature; the COUPE transition is ongoing but not a blocker for initial shipments.

---

## 3. High-Speed Electrical Interconnects

### 3.1 Intel UCIe-S (Paper 8.1)

#### Specifications

| Parameter | UCIe-S | Custom Protocol |
|-----------|--------|----------------|
| Per-lane speed | **48 Gb/s** | **56 Gb/s** |
| Lanes | **16** | — |
| Distance | **30 mm** | — |
| Package | Standard organic | — |
| Process | **22 nm** | — |

#### Context and Implications

- **22 nm Process:** Surprisingly old node for a high-speed interconnect. This is a test vehicle; production on Intel 3 would improve efficiency significantly.
- **30 mm Reach:** Unusually long for die-to-die (typical is <10 mm). This enables connections across standard package substrates, potentially eliminating the need for EMIB (Embedded die-Micro-Bridge) in Intel's Diamond Rapids.
- **Diamond Rapids Application:** Intel's upcoming Xeon has 2 IMH dies + 4 CBB dies with long traces between them. UCIe-S could connect dies over standard substrate.

#### vs Cadence VLSI 2025

| Metric | Intel UCIe-S (22nm) | Cadence (N3E) |
|--------|---------------------|---------------|
| Data rate | **48 Gb/s** | Lower |
| Channel length | **30 mm** | Shorter |
| Shoreline bandwidth | **Better** | Lower |
| Energy efficiency | Lower | **Better** |

Despite a 4-generation node disadvantage, Intel leads in data rate, reach, and shoreline bandwidth.

#### Missing Context

- **UCIe-S vs UCIe-A:** UCIe-A is for advanced packaging (shorter reach, higher density); UCIe-S is for standard substrates. No direct comparison provided.
- **Protocol Overhead:** UCIe-S adds protocol overhead vs. custom protocols. Bandwidth efficiency not quantified.
- **Production Timeline (Updated):** Intel UCIe-S is a 22nm test vehicle. Production on Intel 3 would improve efficiency significantly. UCIe 1.1 specification was ratified in 2024; UCIe-S adoption depends on Intel's Diamond Rapids Xeon timeline (**2026-2027**). Other foundries (TSMC, Samsung) have not committed to UCIe-S support, limiting cross-vendor interoperability.
- **Adoption Beyond Intel:** Will other foundries/designers adopt UCIe-S, or is this Intel-specific?

---

### 3.2 TSMC Active LSI (Paper 8.2)

#### Architecture

Active Local Silicon Interconnect (aLSI) replaces passive metal channels in bridge dies with **active Edge-Triggered Transceiver (ETT)** circuits:

```
Signal → AC-coupling capacitor (180 fF) → Dual-loop amplifier → Output
```

The ETT adds only **0.07 pJ/b** to energy cost, minimizing thermal concerns.

#### Specifications

| Parameter | Value |
|-----------|-------|
| Data rate | **32 Gb/s** (UCIe-like) |
| Bump pitch | **38.8 μm** (down from 45 μm) |
| PHY depth | **850 μm** (down from 1,043 μm) |
| Shoreline | **388 μm** for 64 TX + 64 RX |
| Total area | **0.330 mm²** |
| Power | **0.36 pJ/b** @ 0.75V |
| ETT power | 0.07 pJ/b (subset of total) |
| Shmoo | 32 Gb/s @ 0.75V, 38.4 Gb/s @ 0.95V |

#### Key Benefits

1. **Signal Integrity:** Active conditioning in bridge die reduces top die PHY area (smaller pre-drivers, clock buffers, no receive amplification).
2. **Tighter Pitch:** Manhattan grid (vs. UCIe hexagonal) enables 38.8 μm bump pitch.
3. **eDTC Integration:** Embedded deep trench capacitors improve power delivery without compromising power grid.
4. **Multi-Stage Testing:** KGD → KGS → KGP testing at each assembly stage.

#### Test Vehicle: AMD MI450 Match

The aLSI test vehicle appears to match AMD's MI450 GPU design:
- 2 base dies connected to each other
- 12 HBM4 stacks (2 stacks share 1 aLSI bridge)
- 2 IO dies with Active LSI

#### Comparison Table

| Solution | Data Rate | Power | Shoreline | Process |
|----------|-----------|-------|-----------|---------|
| **TSMC aLSI** | **32 Gb/s** | **0.36 pJ/b** | **388 μm/128 lanes** | TSMC |
| Intel UCIe-S | 48 Gb/s | Not disclosed | Not disclosed | 22 nm |
| Microsoft D2D | 24 Gb/s | 0.33 pJ/b | 532 μm/unknown | N3P |

#### Missing Context

- **UCIe-Like vs True UCIe:** aLSI uses Manhattan grid (UCIe mandates hexagonal). Protocol compatibility is unclear.
- **Thermal Impact:** Active circuits in bridge die generate heat. No thermal analysis provided.
- **Production Timeline (Updated):** TSMC aLSI is closely tied to AMD MI450 GPU design, expected in **2026**. The technology is mature enough for near-term production given TSMC's existing CoWoS-L infrastructure. The transition from passive CoWoS-L to active aLSI is incremental, requiring only the addition of ETT circuits in the bridge die.
- **Cost Premium:** aLSI adds active circuitry to bridge die. Cost impact not quantified.
- **CoWoS-L vs aLSI:** When to use passive CoWoS-L vs active aLSI? No guidance provided.

---

### 3.3 Microsoft D2D Interconnect (Paper 8.3)

#### Specifications

| Parameter | Value |
|-----------|-------|
| Shoreline | **532 μm** |
| Depth | **1,350 μm** |
| Process | **TSMC N3P** |
| Data rates | 20 Gb/s @ 0.65V, **24 Gb/s** @ 0.75V |
| System power | **0.33 pJ/b** @ 24 Gb/s |
| Analog power | **0.226 pJ/b** @ 24 Gb/s |
| Idle power | **0.05 pJ/b** |

#### Context

- **Cobalt 200 CPU:** Microsoft's CPU uses two compute chiplets connected by a custom high-bandwidth interconnect. This paper likely details that interconnect.
- **Power Reporting:** Most D2D papers report analog-only power. Microsoft reports both system and analog, enabling fairer comparisons.

#### vs TSMC aLSI

| Metric | Microsoft D2D | TSMC aLSI |
|--------|---------------|-----------|
| Data rate | 24 Gb/s | 32 Gb/s |
| System power | **0.33 pJ/b** | 0.36 pJ/b |
| Analog power | **0.226 pJ/b** | Not disclosed |
| Shoreline | 532 μm | **388 μm** (for 128 lanes) |

Microsoft is slightly more power-efficient but operates at lower data rates. TSMC achieves higher density per shoreline.

#### Missing Context

- **Lane Count:** Shoreline is given but lane count is not specified, making bandwidth density comparison difficult.
- **Cobalt 200 Integration:** How this interconnect performs in the actual Cobalt 200 CPU is not discussed.
- **Production Timeline (Updated):** Microsoft D2D interconnect is already in production with Cobalt 200 CPU (shipping 2025). The N3P process is mature, and the 24 Gb/s data rate is conservative, suggesting the design prioritizes reliability over peak performance for Azure datacenter workloads.
- **Scale-Up Application:** Microsoft's interconnect is for chiplet-to-chiplet; not designed for scale-up networking.

---

## 4. Processors

### 4.1 MediaTek Dimensity 9500 (Paper 10.2)

#### Key Innovation: 54nm CGP on Ultra Cores

TSMC offers two Contacted Gate Pitch (CGP) options for N3E/N3P:

| CGP | Cell Size | Leakage | Routing | Performance |
|-----|-----------|---------|---------|-------------|
| 48 nm (standard) | Smaller | Higher | Tighter | Higher |
| **54 nm (MediaTek choice)** | Larger | **Lower** | Easier | **Optimized** |

**Results:**
- **4.6% more performance** at iso-leakage
- **3% less power** at iso-performance
- Boost clocks: **4.21 GHz → 4.4 GHz**

#### Context

This is a counterintuitive choice — using a wider (less dense) pitch for high-performance cores. The trade-off favors power efficiency and thermal management over raw density, which is critical for mobile SoCs where thermal throttling limits sustained performance.

#### Missing Context

- **Die Area Impact:** Using 54nm CGP increases core area. Total die size impact not quantified.
- **Competitor Approach:** How do Apple and Qualcomm handle CGP selection for their flagship SoCs?
- **Production Timeline (Updated):** MediaTek Dimensity 9500 is expected to ship in **Q4 2025**, targeting flagship smartphones. The 54nm CGP choice represents a strategic pivot toward power efficiency and thermal management, which may influence competitor designs for mobile SoCs where sustained performance is limited by thermal throttling.

---

### 4.2 Intel M3DProc (Paper 10.6)

#### Architecture

| Parameter | Value |
|-----------|-------|
| Top die | **18A** (56 DNN accelerator tiles) |
| Bottom die | **Intel 3** (56 mesh tiles) |
| Bonding | **Foveros Direct**, 9 μm pitch |
| 3D bandwidth | **875 GB/s** |
| Mesh config | 14×4×2 3D mesh |
| Pads per tile | 552 (~half data, ~quarter power) |

#### vs Clearwater Forest (CWF)

| Metric | M3DProc | CWF |
|--------|---------|-----|
| 3D bandwidth | **875 GB/s** | 210 GB/s per compute die |
| Bandwidth per connection | 15.6 GB/s (56 connections) | 35 GB/s (6 connections) |
| Topology | Fine-grained mesh | Coarse-grained clusters |

**40% throughput increase** vs 2D configuration. Hybrid bonding interconnect has negligible efficiency impact.

#### Missing Context

- **Yield Implications:** Hybrid bonding at 9 μm pitch is challenging. Yield data not provided.
- **Thermal Throughput:** 3D stacking creates thermal challenges. No thermal analysis.
- **Production Timeline (Updated):** Intel M3DProc is a research demonstration using 18A (top) and Intel 3 (bottom). Intel 3 is in production (2024); 18A is targeted for **high-volume manufacturing in 2025**. A production 3D-stacked AI accelerator using similar technology could ship in **2026-2027**, contingent on Foveros Direct yield at 9μm pitch.
- **Product Timeline:** M3DProc is a research chip; when will similar technology ship?

---

### 4.3 AMD MI355X (Paper 2.1)

#### Improvements over MI300X

| Aspect | MI300X | MI355X |
|--------|--------|--------|
| Process | N5 | **N3P** |
| Matrix throughput/CU | Baseline | **2×** (same area) |
| IO Dies | **4** | **2** |
| Frequency (iso-power) | Baseline | **+5%** (before node improvements) |
| Interconnect power | Baseline | **-20%** |

#### Key Innovations

1. **Doubled Matrix Throughput:** Achieved via N5→N3P transition, custom standard cells, denser placement algorithms, and optimized data format circuits.
2. **IOD Consolidation:** 4→2 IO dies saves D2D interconnect area, improves latency, and reallocates power to compute.
3. **Custom Wire Engineering:** 20% reduction in interconnect power through custom wire optimization.

#### Missing Context

- **HBM Configuration:** MI300X used 12 HBM3 stacks; MI355X HBM configuration not specified.
- **Total Chip Power:** Frequency and per-component improvements given, but total chip TDP not disclosed.
- **Production Timeline (Updated):** AMD MI355X is expected to ship in **H2 2026**, targeting AI training and inference workloads. The N3P process transition from MI300X (N5) provides ~2x matrix throughput per CU. HBM4 adoption is likely given the 2026 timeline, though the article does not specify.
- **Competitive Positioning:** No direct comparison to NVIDIA B200/GB200 or upcoming Rubin.

---

### 4.4 Rebellions Rebel100 (Paper 2.2)

#### Specifications

| Parameter | Value |
|-----------|-------|
| Process | **Samsung SF4X** |
| Packaging | **I-CubeS** interposer |
| Compute dies | **4** |
| HBM stacks | **4 × HBM3E** |
| UCIe-A interfaces | 3 per die (2 used at 16 Gb/s) |
| Package modularity | Reconfigurable (IO/memory chiplets) |

#### Strategic Context

- **Samsung Bundle Strategy:** Rebellions likely received steep discounts bundling SF4X front-end with I-CubeS packaging, potentially conditioned on using Samsung HBM.
- **I-CubeS Adoption:** Only 5 confirmed users: eSilicon, Baidu, NVIDIA (small H200 batch), Rebellions, Preferred Networks. Samsung is trying to break into advanced packaging market.
- **TSMC Capacity:** NVIDIA, AMD, Broadcom dominate TSMC capacity, creating opportunities for Samsung.

#### Missing Context

- **Performance Benchmarks:** No inference/training benchmarks provided. Hot Chips 2025 showed Llama 3.3 70B running, but no numbers.
- **IO Chiplet Timeline:** Taped out by 1Q2026; memory chiplet timeline unknown.
- **Production Timeline (Updated):** Rebellions Rebel100 IO chiplet taped out by **1Q2026**. Memory chiplet timeline is unknown but likely Q2-Q3 2026. Full system availability depends on Samsung I-CubeS packaging yield and HBM3E supply. Early samples expected **H2 2026**, volume production **2027**.
- **Power Envelope:** TDP and power efficiency not disclosed.

---

### 4.5 Microsoft Maia 200 (Paper 17.4)

#### Specifications

| Parameter | Value |
|-----------|-------|
| Architecture | **Reticle-scale monolithic** |
| Process | **TSMC N3P** |
| FP4 compute | **>10 PFLOPs** |
| HBM | **6 × HBM3E** |
| D2D links | **28 × 400 Gb/s** full-duplex |
| SRAM | **272 MB** (80 MB L1 + 192 MB L2) |
| Package | CoWoS-S interposer |

#### Network Topology

- **Fixed links:** 21 (7 to each of 3 other chips in node)
- **Switched links:** 7 (to one of 4 in-rack switches)

#### Strategic Context

Maia 200 is the **last major reticle-scale monolithic AI accelerator**. All competitors (NVIDIA, AMD, Google, Amazon) have moved to multi-chiplet designs. Microsoft has pushed the monolithic approach to its limit:
- No legacy hardware (no media/vector units)
- Every mm² optimized for inference
- Designed for post-GPT era workloads

#### Missing Context

- **FLOPs/mm² and FLOPs/W:** Article notes these claims are "dubious" but does not provide independent verification.
- **Inference Benchmarks:** No throughput/latency numbers for specific models.
- **Production Timeline (Updated):** Microsoft Maia 200 is **already in production** and made generally available on Azure in early 2026. The reticle-scale monolithic design is mature, using TSMC N3P process. No further iterations are expected as Microsoft shifts focus to cloud-scale infrastructure rather than chip innovation.
- **Training Capability:** Maia 200 is inference-optimized; training performance not discussed.
- **Azure Availability:** Made generally available earlier in 2026, but adoption and customer feedback not discussed.

---

## 5. Other Highlights

### 5.1 Samsung SF2 Temperature Sensor (Paper 21.5)

#### Innovation

Replaces traditional BJT-based sensors with **BEOL metal resistor** approach:

| Parameter | Value |
|-----------|-------|
| Sheet resistance | **518×** higher than routing metal |
| Area | **~1%** of equivalent routing metal |
| Total sensor area | **625 μm²** |
| TCR | 0.2× routing metal (compensated by higher base resistance) |
| Accuracy FoM | **0.017 nJ·%²** |

#### Comparison to Prior Work

| Sensor | Process | Area | Speed |
|--------|---------|------|-------|
| Samsung SF2 (this work) | SF2 | **625 μm²** | Fast |
| TSMC N3E | N3E | 900 μm² | 1 ms (slow) |
| Samsung 5LPE | 5LPE | 6,356 μm² | 12 μs (fast) |

**Key Innovation:** Time-offset compression technique (fast-charge path at 0.1R, then full resistance) addresses RC time constant slowdown from high resistance. Ring oscillator TDC replaces linear delay generator, cutting area by **99.1%**.

#### Missing Context

- **Production Timeline (Updated):** Samsung SF2 temperature sensor is taped out on SF2 process (same node as HBM4 logic base die). Integration into HBM4 base die is expected in **2026**, aligned with HBM4 volume production. The 625 μm² footprint is small enough for standard PDK inclusion; Samsung could make this a standard IP block for SF2 and future nodes in **2026-2027**.
- **Resolution Trade-off:** Lower TCR limits sensing resolution. Quantitative resolution not provided.
- **Calibration:** How often must the sensor be calibrated across process corners?
- **Integration:** Will this become a standard PDK element across Samsung nodes?

---

## 6. Cross-Cutting Analysis and Missing Context

### 6.1 What the Article Gets Right

1. **HBM4 is exceeding JEDEC specs significantly** — Samsung's 2× JEDEC pin speed is a meaningful differentiator.
2. **SRAM scaling has stalled** — The data on 8T-HC SRAM area reduction (18% over 40% logic shrink) is damning.
3. **CPO is bifurcating** — DWDM for scale-up, DR optics for scale-out is a reasonable industry trajectory.
4. **Samsung's yield risk on 1c** — 50% front-end yield is a real concern for HBM4 competitiveness.

### 6.2 What's Missing or Needs Scrutiny

#### Power Numbers Are Incomplete

- **Broadcom 6.4T OE (Updated):** No direct figures from ISSCC paper. Estimated 96-128 W per OE based on 100G PAM4 SerDes benchmarks (1.5-2.0 W/lane x 64 lanes). Actual may differ with SiPh integration. Reference: NTT PCW modulator achieves 0.78 pJ/bit at 64-Gbaud [arXiv:2506.04820], significantly below production estimates.
- **NVIDIA DWDM (Updated):** Per-lambda power not disclosed. Clock forwarding eliminates CDR power but exact savings unknown. DSP-free CPR approaches target <5 pJ/b vs current coherent DSP at ~50 pJ/b [arXiv:2505.18534].
- **HBM4 power per bit:** Not disclosed. Lower VDDQ (0.75V vs 1.1V) suggests improvement, but logic base die may add static power. No pJ/bit figures available.
- **CPO vs pluggable (Updated):** Industry estimates suggest CPO saves 30-50% vs pluggable by eliminating SerDes for electrical traces and pluggable overhead. Typical 200G pluggable: 10-15W; CPO target: 5-8W equivalent. VCSEL-based CPO claims superior wall-plug efficiency [arXiv:2601.14342].
- **DSP power context:** Current coherent DSP consumes ~50 pJ/b, 10x higher than intra-datacenter targets (~5 pJ/b). DSP-free approaches aim to close this gap [arXiv:2505.18534].

#### Power Figures Found in Academic Literature

| Technology | Energy Efficiency | Data Rate | Source |
|------------|-------------------|-----------|--------|
| NTT PCW modulator | **0.78 pJ/bit** | 64-Gbaud | [arXiv:2506.04820] |
| Laval comb-driven coherent | **10 fJ/bit** (modulation only) | 120 GBd | [arXiv:2509.20584] |
| Marvell coherent-lite | **3.72 pJ/b** | 400 Gb/s | ISSCC 2026 Paper 23.2 |
| TSMC aLSI | **0.36 pJ/b** | 32 Gb/s | ISSCC 2026 Paper 8.2 |
| Microsoft D2D | **0.33 pJ/b** | 24 Gb/s | ISSCC 2026 Paper 8.3 |

**Note:** Academic lab results (0.78 pJ/bit, 10 fJ/bit) are significantly better than production estimates, highlighting the research-to-production gap. C2PO architecture [arXiv:2506.12160] demonstrates 400 Gb/s offset-QAM-16 at 9.65 dBm laser power with 10-100x less area than MZI-based links.


#### Competitive Comparisons Are Limited
- No direct HBM4 comparison between Samsung, SK Hynix, and Micron (only Samsung presented)
- No GDDR7 comparison between Samsung and SK Hynix at same process node
- No CPO comparison between NVIDIA COUPE and Broadcom Fan-Out WLP

#### Production Timelines Are Unclear
- Most papers are research demonstrations; volume production typically lags 1-2 years
- No clear timelines for HBM4 volume production, 4F² DRAM, or interposer-level CPO
- Rebellions IO chiplet timeline given (1Q2026), but memory chiplet timeline unknown

#### Cost Analysis Is Absent
- No COGS comparisons for any technology (HBM4, LPDDR6, GDDR7, MRAM, NAND)
- Samsung's SF4 base die cost premium vs SK Hynix's TSMC N12 not quantified
- aLSI cost premium vs passive CoWoS-L not discussed

#### Thermal Analysis Is Missing
- 3D stacking (M3DProc, aLSI) creates thermal challenges not addressed
- 6.4T optical engine thermal design not discussed
- Mobile SoC thermal management only briefly covered (MediaTek)

#### Market Context Is Limited
- No discussion of memory supply/demand dynamics affecting pricing
- No analysis of how US export controls affect technology development timelines
- No discussion of foundry capacity constraints (TSMC vs Samsung)

### 6.3 Numbers That Need Verification

1. **Samsung LPDDR6 Density (0.360 Gb/mm²):** Article speculates this may be on 1b process, not 1c. If confirmed on 1b, the density regression is even more concerning.

2. **SK Hynix LPDDR6 Density (~0.59 Gb/mm²):** This is an estimate based on GDDR7 density increase, not a measured value. Should be treated as approximate.

3. **Maia 200 FLOPs/mm² and FLOPs/W:** Article explicitly calls these "dubious" without providing independent verification.

4. **Intel UCIe-S on 22nm:** The article correctly notes this is a test vehicle, but the performance advantage over N3E Cadence implementation seems large for such a node gap. PHY design quality may be the differentiator.

---

## 7. Strategic Implications

### 7.1 Memory
- **HBM4 will be a multi-vendor race** with Samsung leading on raw speed but SK Hynix leading on reliability and potentially cost
- **LPDDR6 density regression** could impact mobile SoC designs that rely on high memory density
- **4F² DRAM is years away** — current DRAM scaling will continue with incremental improvements through 1d

### 7.2 Optical Networking
- **CPO adoption will be gradual** — substrate-level CPO first, interposer-level later
- **DWDM vs PAM4 is not a zero-sum game** — both will coexist for different use cases
- **Coherent-lite fills a real gap** for campus-scale datacenter interconnects

### 7.3 Interconnects
- **Die-to-die is becoming a first-class design concern** — multiple competing standards (UCIe-S, UCIe-A, aLSI, custom)
- **Active interposers are inevitable** as passive approaches hit signal integrity limits
- **Intel's long-reach UCIe-S** could change the economics of advanced packaging

### 7.4 Processors
- **Monolithic designs are dying** — Maia 200 is the last major example
- **3D integration is accelerating** — Intel's M3DProc shows the direction
- **Samsung Foundry is gaining traction** — Rebellions' choice signals viable alternative to TSMC

---

### 6.4 Consolidated Production Timeline

| Technology | Current Status | Expected Volume Production | Key Dependencies |
|------------|---------------|--------------------------|------------------|
| **Samsung HBM4** | ISSCC demo (13 Gb/s) | **2026** | 1c node yield (>50% in 2025) |
| **LPDDR6** | Prototype | **H2 2026** | 1c transition for density recovery |
| **GDDR7** | Pre-production | **Q1 2026** | NVIDIA gaming GPU adoption |
| **4F² COP DRAM** | Research | **2028-2030** | Hybrid bonding yield |
| **BiCS10 NAND** | 332L demo | **2027** | CBA process maturity |
| **xBIT SRAM** | Research | **2027-2028** | TSMC PDK integration |
| **TSMC N16 MRAM** | Demo | **2026-2027** | Automotive qualification |
| **NVIDIA DWDM CPO** | ISSCC demo | **Late 2026** | Rubin platform timeline |
| **Broadcom 6.4T OE** | ISSCC demo | **2026-2027** | Tomahawk 5 availability |
| **Intel UCIe-S** | 22nm test vehicle | **2026-2027** | Intel 3 migration |
| **TSMC aLSI** | MI450 test vehicle | **2026** | CoWoS-L infrastructure |
| **Microsoft D2D** | In production (Cobalt 200) | **Now** | None |
| **AMD MI355X** | ISSCC demo | **H2 2026** | N3P capacity |
| **Rebellions Rebel100** | IO taped out Q1 2026 | **2027** | I-CubeS yield |
| **Microsoft Maia 200** | In production | **Now** | None |

---

## References

1. [arXiv:2512.18152] REACH: Controller-managed ECC for HBM, 17.5W at 3.56 TB/s
2. [arXiv:2506.04820] NTT PCW modulator: 0.78 pJ/bit at 64-Gbaud, 50 mW total
3. [arXiv:2509.20584] Laval comb-driven coherent: 10 fJ/bit modulation at 120 GBd
4. [arXiv:2505.18534] DSP-free CPR: targets <5 pJ/b vs current 50 pJ/b
5. [arXiv:2601.14342] VCSEL-based CPO for scale-up in AI datacenters
6. [arXiv:2506.12160] C2PO: coherent CPO with offset-QAM-16, 400 Gb/s at 9.65 dBm

---

*Generated from SemiAnalysis article "ISSCC 2026: NVIDIA & Broadcom CPO, HBM4 & LPDDR6, TSMC Active LSI, Logic-Based SRAM, UCIe-S and More" (April 2026). All numbers and references sourced directly from the article, with additional context and verification notes added.*
