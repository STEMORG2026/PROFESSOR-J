# Generalization Benchmark Suite (v0.5)

## Overview

To prove that PROFESSOR-J possesses a general-purpose game development capability rather than domain-specific heuristics, 8 novel game genres are benchmarked:

| Benchmark | Genre / Domain | Key Mechanic & Invariant | Multi-File Repair Scenario |
|---|---|---|---|
| **1** | Stealth / Detection | Vision cone detection radius; no phantom detections | Single-file radius inversion repair |
| **2** | Farming / Production | Resource conservation; irrigation consumes water | Single-file sign error repair |
| **3** | Turn-Based Tactical Combat | Action points check; attacks cost AP | **Multi-File**: `ActionPointSystem` + `CombatResolver` |
| **4** | Rhythm / Timing | Note window timing $|t_{hit} - t_{note}| \le window$ | Single-file timing window bounds repair |
| **5** | Fishing / Catch | Line tension accumulation and maximum limit | Single-file tension clamp and snap |
| **6** | Auction / Trading | Budget escrow hold; bids cannot exceed available funds | **Multi-File**: `BudgetEscrow` + `BidValidator` |
| **7** | Survival / Hunger | Metabolism decay and starvation health drain | **Multi-File**: `MetabolismSystem` + `VitalsManager` |
| **8** | Procedural Dungeon / Loot | Seeded PRNG stream determinism | Seed reproduction verification |
