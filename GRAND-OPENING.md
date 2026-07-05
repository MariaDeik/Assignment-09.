# Grand Opening — Maria's AI Hardware Store

## Store Details

- **Store Name:** Maria's AI Hardware Store
- **Live URL:** http://98.84.121.90:8080

---

## Original Brief

Build a web app called "Maria's AI Hardware Store".

Use:
- Python Flask
- PostgreSQL
- port 8080
- systemd so it stays running after logout/reboot

The store must:
1. Be live at http://98.84.121.90:8080
2. Show the name "Maria's AI Hardware Store"
3. Sell real NVIDIA AI hardware with real prices, GPU memory, power draw, and simple explanations
4. Recommend builds for at least 3 large open-source AI models around 100B+ parameters
5. Show memory math: parameters in billions × 1 GB + 20%
6. Have paths for Small Startup and Mid-size Company
7. Explain clusters and calculate combined memory, power, and price
8. Compare power to homes: 1 home = 1200W
9. Compare energy to EV battery: 1 EV battery = 90 kWh
10. Have quote request form saving name, contact, and selected build into PostgreSQL
11. Show saved requests at /requests with request numbers

---

## Three Checks

**Check 1 — Homepage loads with correct store name**
```
curl -s http://98.84.121.90:8080/ | grep "Maria's AI Hardware Store"
```
Expected: line containing `Maria's AI Hardware Store`

**Check 2 — Quote form saves to the database**
```
curl -s -X POST http://98.84.121.90:8080/quote \
  -d "name=Test+User&contact=test@example.com&selected_build=Small+Startup+Starter+Pack" | grep "submitted"
```
Expected: line containing `submitted`

**Check 3 — Requests page shows saved quote with a request number**
```
curl -s http://98.84.121.90:8080/requests | grep "Test User"
```
Expected: line containing `Test User` and a `#N` request number
