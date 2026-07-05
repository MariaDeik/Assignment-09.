# Grand Opening — Maria's AI Hardware Store

## Store Details

- **Store Name:** Maria's AI Hardware Store
- **Live URL:** http://98.84.121.90:8080

---

## The Brief I Wrote

Build a web application called "Maria's AI Hardware Store" — a professional AI infrastructure storefront running on AWS EC2.

**Technology stack:**
- Python and Flask for the web application
- PostgreSQL for storing quote requests
- systemd so the application stays running after logout and reboot
- Port 8080
- Amazon Linux 2023 on AWS EC2

**The store must:**

1. Be live and accessible at http://98.84.121.90:8080
2. Show the name "Maria's AI Hardware Store" with the subtitle "Enterprise AI Infrastructure • GPU Clusters • NVIDIA Solutions"
3. Sell real NVIDIA AI hardware (H200 SXM5, H100 SXM5, H100 PCIe, A100 SXM4, A100 PCIe, RTX 6000 Ada, RTX 4090) with real market prices, GPU memory, power draw, and plain-English explanations
4. Feature the NVIDIA GB300 NVL72 as a flagship enterprise product with full specifications
5. Recommend pre-built configurations for at least three team sizes: Small Startup, Mid-size Company, and Enterprise
6. Show memory math for large open-source AI models (Llama 405B, Falcon 180B, DeepSeek-V2 236B, Mixtral 141B) using the formula: parameters in billions × 1 GB × 1.2 overhead = minimum VRAM required
7. Explain what AI clusters are, how multi-GPU systems work, and include a visual cluster diagram
8. Compare GPU power draw to real-world equivalents: homes (1 home = 1,200 W) and EV batteries (1 EV = 90 kWh)
9. Include a working quote request form that saves name, contact, and selected build to PostgreSQL
10. Show all submitted quote requests at /requests with assigned request numbers
11. Include WhatsApp contact (+1 786 213 4550) and email (mdwork3003@gmail.com) with pre-filled professional messages
12. Include an About Maria section with her bio, contact details, and buttons
13. Include a Built With section showing: Python, Flask, PostgreSQL, Amazon EC2, Linux, systemd, HTML, CSS, JavaScript
14. Include a pricing disclaimer that prices are approximate and vary by vendor
15. Display a professional footer with store name, tagline, contact information, technology credits, and copyright © 2026 Maria Deiko
16. Be fully responsive for mobile and desktop

---

## What I Checked Before Opening

**Check 1 — AI model memory calculation verified manually**

I manually verified the GPU memory calculation for Meta Llama 3.1 405B using the formula:

```
parameters × 1 GB × 1.2 overhead = minimum VRAM required
405 × 1 GB = 405 GB raw weight
405 GB × 1.2 = 486 GB minimum VRAM
```

The store shows this calculation correctly and recommends the right number of H100 or H200 GPUs to run the model.

**Check 2 — Quote request form saves to PostgreSQL and appears on /requests**

I submitted a quote request through the form at /quote with my name, contact, and a selected build. The store confirmed the submission, assigned it a request number, and it appeared correctly on the /requests page with the request number, name, contact, build name, and timestamp.

```bash
curl -s -X POST http://98.84.121.90:8080/quote \
  -d "name=Test+User&contact=test@example.com&selected_build=Small+Startup+Starter+Pack" \
  | grep "saved to our database"
```

Expected: line containing `saved to our database`

```bash
curl -s http://98.84.121.90:8080/requests | grep "Test User"
```

Expected: row containing `Test User` with a `#N` request number

**Check 3 — GPU memory and power explanations reviewed**

I reviewed the GPU cards and confirmed that each one explains its memory, power draw, electricity cost per year, equivalent home power usage, cooling requirements, deployment environment, and recommended workload — all in plain English without requiring the reader to interpret a raw spec sheet.

---

## Three Verification Checks

**Check 1 — Homepage loads with correct store name**
```bash
curl -s http://98.84.121.90:8080/ | grep "Maria's AI Hardware Store"
```
Expected: line containing `Maria's AI Hardware Store`

**Check 2 — Quote form saves to the database**
```bash
curl -s -X POST http://98.84.121.90:8080/quote \
  -d "name=Test+User&contact=test@example.com&selected_build=Small+Startup+Starter+Pack" \
  | grep "saved to our database"
```
Expected: line containing `saved to our database`

**Check 3 — Requests page shows saved quote with a request number**
```bash
curl -s http://98.84.121.90:8080/requests | grep "Test User"
```
Expected: line containing `Test User` and a `#N` request number
