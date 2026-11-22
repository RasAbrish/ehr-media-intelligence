# Manual review of AI summaries

Score each summary 1 to 5 for accuracy, completeness and concision against the source records (open the patient in the app). Gate: mean of all scores ≥ 4. Patients are listed by key only.

Provider groq, model openai/gpt-oss-120b, prompt `v1`.

| # | Patient key | Accuracy | Completeness | Concision | Notes |
|---|---|---|---|---|---|
| 1 | `b09c3338-b85f-574e-bb8e-96122179329a` | | | | |
| 2 | `2d4abc2d-9d2a-5cd0-8fa5-062d82f33c5d` | | | | |
| 3 | `0f6e25ff-b865-56a3-bec9-d56eb2677327` | | | | |
| 4 | `dae3655d-23fb-5567-8ed0-ec11f2c68f74` | | | | |
| 5 | `4f262ef9-5924-5442-89b3-8414fe174f2d` | | | | |
| 6 | `4a95631a-e561-5cb3-abd7-bd9c21cd03d5` | | | | |
| 7 | `4603a76a-5a91-57e0-8fae-290b6e68b1af` | | | | |
| 8 | `320afa77-5348-5e0d-83c2-f46f8ce750e9` | | | | |
| 9 | `f4b38133-769f-5c3b-8bdc-9958c66c2960` | | | | |
| 10 | `218cd559-8aa9-5fa8-b755-355f699bb599` | | | | |

## 1. `b09c3338`

```
Chief concern:
Acute ischemic stroke presenting with right arm weakness and expressive aphasia.
Key diagnoses:
- Acute ischemic stroke left MCA territory (active)
Recent media:
- Troponin I <0.01 N
- Acute left MCA infarct, diffusion restriction, no hemorrhage
- LDL 168 H, HDL 52 N, Triglycerides 88 N, total cholesterol 179 N
- Neurology consult: stroke assessment, aspirin, high‑intensity atorvastatin
Flagged anomalies:
- LDL cholesterol 168 mg/dL, above reference range (moderate)
Overview:
34‑year‑old female with acute left MCA ischemic stroke; labs show elevated LDL; started on aspirin and high‑intensity atorvastatin.
```

## 2. `2d4abc2d`

```
Chief concern:
Treated for right lower lobe community-acquired pneumonia.
Key diagnoses:
- Community-acquired pneumonia (active)
Recent media:
- Chest X-ray: right lower lobe consolidation with air bronchograms
- WBC 16.3 ×10^3/µL (high), platelets 202, hemoglobin 14
- Discharge summary: completed IV antibiotics, plan oral amoxicillin‑clavulanate
Flagged anomalies:
- Elevated WBC 16.3 ×10^3/µL, moderate severity (moderate)
Overview:
75‑year‑old female admitted with community‑acquired pneumonia, CURB‑65 2; treated with ceftriaxone, azithromycin, then oral amoxicillin‑clavulanate; WBC elevated during admission.
```

## 3. `0f6e25ff`

```
Chief concern:
Acute exacerbation of COPD presenting with increased dyspnea and sputum.
Key diagnoses:
- Acute exacerbation of COPD (active)
- Emphysematous changes of lung (suspected)
Recent media:
- Chest X-ray: hyperinflated lungs, flattened diaphragms, no acute infiltrate
- WBC 12.9 H
- Basic metabolic panel within normal limits
Flagged anomalies:
- Elevated WBC 12.9 ×10³/µL, moderate severity (moderate)
Overview:
68‑year‑old female with known COPD admitted for an acute exacerbation; imaging shows emphysematous changes, labs reveal leukocytosis.
```

## 4. `dae3655d`

```
Chief concern:
Community-acquired pneumonia presenting with fever, productive cough, and pleuritic chest pain.
Key diagnoses:
- Community-acquired pneumonia (active)
Recent media:
- Chest X-ray: focal right lower lobe consolidation with air bronchograms, consistent with pneumonia.
- WBC 17.1 x10^3/uL (high).
Flagged anomalies:
- WBC 17.1 x10^3/uL, markedly elevated (moderate)
Overview:
22-year-old female admitted for community-acquired pneumonia; imaging confirms right lower lobe infiltrate; labs show leukocytosis; started on ceftriaxone and azithromycin.
```

## 5. `4f262ef9`

```
Chief concern:
Evaluation of chronic kidney disease with ongoing hyperkalemia.
Key diagnoses:
- Chronic kidney disease stage 3b (active)
- Hyperkalemia (active)
Recent media:
- Renal US: small kidneys, increased echogenicity, no hydronephrosis
- CBC: WBC 7.7 N, Platelets 222 N, Hemoglobin 13.6 N
- BMP: K 5.8 H, Creatinine 2.61 H, BUN 37 H
Flagged anomalies:
- Potassium 5.8 mmol/L, moderately high (moderate)
- Creatinine 2.61 mg/dL, moderately high (moderate)
- Urea nitrogen 37 mg/dL, moderately high (moderate)
Overview:
26-year-old male with CKD stage 3b and hyperkalemia; lisinopril discontinued, potassium binder initiated, imaging confirms chronic renal changes.
```

## 6. `4a95631a`

```
Chief concern:
New diagnosis of left breast invasive ductal carcinoma.
Key diagnoses:
- Invasive ductal carcinoma of left breast, ER/PR positive, HER2 negative (suspected)
Recent media:
- CBC: Hgb 14.6 N, Plt 283 N, WBC 5.8 N
- Mammogram/US: BI-RADS 5, 2.4 cm spiculated mass left breast, no axillary adenopathy
- Core needle biopsy: invasive ductal carcinoma, Nottingham grade 2, ER+/PR+, HER2-
Flagged anomalies:
- none
Overview:
78‑year‑old male with newly identified left breast invasive ductal carcinoma, hormone‑receptor positive; imaging shows BI‑RADS 5 lesion, pathology confirms grade 2 cancer; plan lumpectomy with sentinel node biopsy.
```

## 7. `4603a76a`

```
Chief concern:
Treated for urosepsis during recent admission.
Key diagnoses:
- Urosepsis (active)
- E. coli urinary tract infection (suspected)
Recent media:
- Lactate 3.7 mmol/L (high)
- ED note: sepsis, lactate 3.7, WBC 23.1
Flagged anomalies:
- Lactate 3.7 mmol/L, above reference range (moderate)
Overview:
36‑year‑old male admitted for urosepsis; urine culture grew E. coli; elevated lactate normalized after fluids; discharged on cefpodoxime.
```

## 8. `320afa77`

```
Chief concern:
Fatigue, cold intolerance and weight gain; labs reveal primary hypothyroidism.
Key diagnoses:
- Primary hypothyroidism (active)
Recent media:
- TSH 11.22 H; Free T4 0.5 L
- HDL 46 N; LDL 91 N; Cholesterol 198 N; Triglycerides 122 N
- Thyroid US: diffusely heterogeneous gland, no nodules – suggests chronic thyroiditis
Flagged anomalies:
- TSH 11.22 mIU/L, above reference range (moderate)
- Free T4 0.5 ng/dL, below reference range (moderate)
- MRN shared with another person; identity flagged for review (low)
Overview:
29-year-old male with primary hypothyroidism; elevated TSH, low free T4, ultrasound consistent with chronic thyroiditis; started levothyroxine.
```

## 9. `f4b38133`

```
Chief concern:
Fatigue, cold intolerance, and weight gain concerning primary hypothyroidism.
Key diagnoses:
- Primary hypothyroidism (active)
Recent media:
- Free T4 0.61 L, TSH 13.12 H
- Thyroid US: diffusely heterogeneous gland, no nodules (suggestive of chronic thyroiditis)
Flagged anomalies:
- Free T4 0.61 ng/dL below reference range (moderate)
- TSH 13.12 mIU/L above reference range (moderate)
Overview:
31-year-old male with primary hypothyroidism; labs confirm high TSH and low free T4, ultrasound suggests chronic thyroiditis; started levothyroxine.
```

## 10. `218cd559`

```
Chief concern:
Sepsis from urinary source presenting with fever, confusion, and dysuria.
Key diagnoses:
- Urosepsis (active)
Recent media:
- WBC 19.7 H
- Lactate 4.7 HH
- ED assessment of sepsis, lactate 4.7, WBC 19.7
Flagged anomalies:
- Lactate 4.7 mmol/L, critically high (high)
- WBC 19.7 x10^3/uL, elevated (moderate)
Overview:
70-year-old male treated for urinary source sepsis; cultures grew E. coli, received cefpodoxime; lactate and WBC normalized after fluids.
```
