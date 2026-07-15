from flask import Flask, request, redirect, url_for
import psycopg2
import psycopg2.extras
import json
import html

app = Flask(__name__)

DB_CONFIG = {
    'dbname': 'hardware_store',
    'user': 'storeuser',
    'password': 'storepass123',
    'host': 'localhost',
    'port': 5432
}

def get_db():
    return psycopg2.connect(**DB_CONFIG)

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS quote_requests (
            id SERIAL PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            contact VARCHAR(200) NOT NULL,
            selected_build TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

def _e(w):
    return f"${round(w / 1000 * 8760 * 0.12):,}/yr"

def min_vram_gb(params_b, precision_factor=1.0):
    """Minimum VRAM (GB) to load a model: parameters x 1 GB x precision + 20% overhead."""
    return round(params_b * precision_factor * 1.2)

GPUS = [
    {
        "name": "NVIDIA H200 SXM5",
        "memory_gb": 141, "power_w": 700, "price": 44000,
        "description": "The most powerful AI GPU ever built. 141 GB HBM3e at 4.8 TB/s. Purpose-built for frontier AI model training and the most memory-demanding workloads.",
        "tier": "enterprise", "type": "server",
        "badge_icon": "\U0001f680", "badge_label": "Frontier AI", "badge_cls": "bdg-frontier",
        "best_for": "Frontier model training",
        "cooling": "Liquid cooling required",
        "deployment": "Data center rack (SXM baseboard)",
        "workload": "Training 100B–400B+ parameter models",
        "warranty": "1-year NVIDIA manufacturer warranty",
        "availability": "4–6 week lead time",
    },
    {
        "name": "NVIDIA H100 SXM5",
        "memory_gb": 80, "power_w": 700, "price": 32000,
        "description": "Industry standard for large-scale AI training. 80 GB HBM3 with NVLink for seamless multi-GPU scaling within and across nodes.",
        "tier": "enterprise", "type": "server",
        "badge_icon": "\U0001f525", "badge_label": "Most Popular", "badge_cls": "bdg-popular",
        "best_for": "Large model training & serving",
        "cooling": "Liquid cooling required",
        "deployment": "Data center rack (DGX/HGX systems)",
        "workload": "Training and serving 70B–180B models",
        "warranty": "1-year NVIDIA manufacturer warranty",
        "availability": "2–4 week lead time",
    },
    {
        "name": "NVIDIA H100 PCIe",
        "memory_gb": 80, "power_w": 350, "price": 26000,
        "description": "Full H100 performance in a standard PCIe slot. Half the power of SXM5. Best for AI inference in existing rack infrastructure.",
        "tier": "enterprise", "type": "pcie",
        "badge_icon": "\U0001f3e2", "badge_label": "Enterprise", "badge_cls": "bdg-enterprise",
        "best_for": "Large model inference",
        "cooling": "Air cooling compatible",
        "deployment": "Standard PCIe server slot",
        "workload": "Inference on 70B–180B models",
        "warranty": "1-year NVIDIA manufacturer warranty",
        "availability": "1–3 week lead time",
    },
    {
        "name": "NVIDIA A100 SXM4",
        "memory_gb": 80, "power_w": 400, "price": 16000,
        "description": "Proven enterprise workhorse. Previous-generation SXM GPU with 80 GB VRAM. Excellent price/performance for established AI workloads.",
        "tier": "enterprise", "type": "server",
        "badge_icon": "⭐", "badge_label": "Best Value", "badge_cls": "bdg-value",
        "best_for": "Training, cost-effective workloads",
        "cooling": "Liquid cooling required",
        "deployment": "Data center rack (DGX A100 systems)",
        "workload": "Training 13B–80B models, stable production inference",
        "warranty": "1-year NVIDIA manufacturer warranty",
        "availability": "In stock",
    },
    {
        "name": "NVIDIA A100 PCIe",
        "memory_gb": 80, "power_w": 300, "price": 12500,
        "description": "80 GB A100 in a standard PCIe form factor. Upgrade existing servers without special hardware. Solid choice for inference.",
        "tier": "professional", "type": "pcie",
        "badge_icon": "\U0001f3e2", "badge_label": "Enterprise", "badge_cls": "bdg-enterprise",
        "best_for": "Inference, server hardware upgrades",
        "cooling": "Air cooling compatible",
        "deployment": "Standard PCIe server slot",
        "workload": "Inference on 13B–80B models",
        "warranty": "1-year NVIDIA manufacturer warranty",
        "availability": "In stock",
    },
    {
        "name": "NVIDIA RTX 6000 Ada",
        "memory_gb": 48, "power_w": 300, "price": 7200,
        "description": "The best single professional GPU for small AI teams. 48 GB GDDR6 lets you run 30–40B models without a full data center setup.",
        "tier": "professional", "type": "workstation",
        "badge_icon": "\U0001f4bb", "badge_label": "Workstation", "badge_cls": "bdg-workstation",
        "best_for": "Small team model serving",
        "cooling": "Air cooling (workstation or server)",
        "deployment": "Workstation or standard server",
        "workload": "Inference on 7B–40B models, fine-tuning up to 13B",
        "warranty": "3-year NVIDIA professional warranty",
        "availability": "In stock",
    },
    {
        "name": "NVIDIA RTX 4090",
        "memory_gb": 24, "power_w": 450, "price": 1800,
        "description": "The most affordable serious AI GPU. 24 GB GDDR6X. Ideal for experimentation, fine-tuning small models, and running 7B–13B models in production.",
        "tier": "starter", "type": "consumer",
        "badge_icon": "\U0001f4b0", "badge_label": "Budget", "badge_cls": "bdg-budget",
        "best_for": "Experimentation & fine-tuning",
        "cooling": "Air cooling (desktop case or 4U server)",
        "deployment": "Workstation desktop or dense server",
        "workload": "Inference on 7B–13B models, fine-tuning 7B models",
        "warranty": "3-year NVIDIA consumer warranty",
        "availability": "In stock",
    },
]

for g in GPUS:
    g['elec_year'] = _e(g['power_w'])

GB300 = {
    "name": "NVIDIA GB300 NVL72",
    "gpu_count": 72,
    "per_gpu_memory": 192,
    "memory_gb": 13824,
    "power_w": 120000,
    "price_label": "~$3M+",
    "description": "NVIDIA's next-generation AI factory in a single rack. 72 connected B300 GPUs share memory and compute via NVLink — functioning as one massive 13,824 GB supercomputer. Purpose-built for training frontier models from scratch.",
    "use_cases": [
        "Training 400B+ parameter models from scratch",
        "Running 10+ large models simultaneously",
        "Replacing an entire GPU cluster in one rack",
        "Enterprise AI R&D and frontier research",
    ],
    "specs": [
        ("72", "B300 GPUs"),
        ("192 GB", "VRAM per GPU"),
        ("13,824 GB", "Total VRAM"),
        ("120 kW", "Total Power Draw"),
        ("100 homes", "Equivalent power draw"),
        ("~$3M+", "Starting price"),
    ],
}

COMPARISON = [
    {"name": "RTX 4090",         "memory_gb": 24,    "power_w": 450,    "price_str": "$1,800",   "best_for": "Starter projects, fine-tuning"},
    {"name": "RTX 6000 Ada",     "memory_gb": 48,    "power_w": 300,    "price_str": "$7,200",   "best_for": "Teams running 30–40B models"},
    {"name": "A100 PCIe",        "memory_gb": 80,    "power_w": 300,    "price_str": "$12,500",  "best_for": "Inference workloads"},
    {"name": "H100 PCIe",        "memory_gb": 80,    "power_w": 350,    "price_str": "$26,000",  "best_for": "Large model inference at scale"},
    {"name": "H100 SXM5",        "memory_gb": 80,    "power_w": 700,    "price_str": "$32,000",  "best_for": "Training + highest throughput"},
    {"name": "H200 SXM5",        "memory_gb": 141,   "power_w": 700,    "price_str": "$44,000",  "best_for": "Frontier model training"},
    {"name": "GB300 NVL72 Rack", "memory_gb": 13824, "power_w": 120000, "price_str": "~$3M+",    "best_for": "AI factory, hyperscale compute"},
]

MODELS = [
    {"name": "Meta Llama 3.1 405B", "params_b": 405,
     "description": "Meta's flagship open-source model. GPT-4 class performance. The gold standard for open-source AI.",
     "use_case": "General AI assistant, coding, reasoning"},
    {"name": "Falcon 180B", "params_b": 180,
     "description": "TII's 180B model trained on 3.5 trillion tokens. Strong multilingual and reasoning performance.",
     "use_case": "Multilingual generation, analysis"},
    {"name": "DeepSeek-V2 236B", "params_b": 236,
     "description": "Mixture-of-Experts design. 236B total parameters, only 21B active per token — highly cost-efficient.",
     "use_case": "Code generation, math, science"},
    {"name": "Mixtral 8x22B (141B)", "params_b": 141,
     "description": "Mistral's MoE model. Fast and capable. 39B active per token means lower serving cost than dense models.",
     "use_case": "Fast inference, instruction following"},
]

BUILDS = {
    "small_startup": {
        "name": "Small Startup Starter Pack", "path": "Small Startup", "gpu": GPUS[5], "count": 4,
        "description": "4× RTX 6000 Ada. 192 GB combined VRAM. Run models up to 150B parameters. Perfect for a team of 5–15 engineers.",
        "use_cases": ["Fine-tuning Llama 70B", "Running Mixtral 8×7B in production", "Rapid model experiments"],
    },
    "mid_company": {
        "name": "Mid-size Company Cluster", "path": "Mid-size Company", "gpu": GPUS[2], "count": 8,
        "description": "8× H100 PCIe. 640 GB combined VRAM. Run the largest open-source models. Production-ready for 50–200 person orgs.",
        "use_cases": ["Full Llama 3.1 405B inference", "Training custom 70B models", "Multi-user AI platform at scale"],
    },
    "enterprise": {
        "name": "Enterprise H200 Cluster", "path": "Enterprise", "gpu": GPUS[0], "count": 16,
        "description": "16× H200 SXM5. 2,256 GB combined VRAM. Train and serve frontier models. For large AI-first organizations.",
        "use_cases": ["Training 400B+ models from scratch", "Serving multiple large models simultaneously", "Full AI research infrastructure"],
    },
}

GB300_QUOTE_OPTION = "GB300 NVL72 Rack — Enterprise Custom"
VALID_BUILD_NAMES = {b['name'] for b in BUILDS.values()} | {GB300_QUOTE_OPTION}

HOME_WATTS = 1200
EV_KWH = 90
CONTACT_EMAIL = "mdwork3003@gmail.com"
WA_DISPLAY = "+1 (786) 213-4550"
WA_FLOAT_LINK = "https://wa.me/17862134550?text=Hello%2C%20I%27m%20interested%20in%20learning%20more%20about%20your%20AI%20hardware%20solutions.%20Could%20someone%20from%20your%20team%20help%20me%20choose%20the%20right%20configuration%3F"
WA_CARD_LINK  = "https://wa.me/17862134550?text=Hello%2C%20I%27m%20interested%20in%20learning%20more%20about%20your%20AI%20hardware%20solutions.%20Could%20someone%20from%20your%20team%20help%20me%20choose%20the%20right%20configuration%3F"

WA_SVG_SM = '<svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>'
WA_SVG_LG = '<svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>'

def wa_card_btn(label="Contact Our Solutions Team"):
    return f'<a class="wa-btn" href="{WA_CARD_LINK}" target="_blank" rel="noopener">{WA_SVG_SM} {label}</a>'

SVG = {}
SVG["server"] = '<svg viewBox="0 0 160 96" xmlns="http://www.w3.org/2000/svg"><rect x="1" y="1" width="158" height="94" rx="5" fill="#07101e" stroke="#1c2e48" stroke-width="1"/><rect x="10" y="14" width="26" height="68" rx="3" fill="#0a1828" stroke="#1e4070" stroke-width="1"/><text x="23" y="50" text-anchor="middle" fill="#1e5090" font-size="7" font-family="monospace">HBM</text><rect x="124" y="14" width="26" height="68" rx="3" fill="#0a1828" stroke="#1e4070" stroke-width="1"/><text x="137" y="50" text-anchor="middle" fill="#1e5090" font-size="7" font-family="monospace">HBM</text><rect x="42" y="10" width="76" height="76" rx="4" fill="#0c1a2e" stroke="#76b900" stroke-width="1.5"/><line x1="42" y1="34" x2="118" y2="34" stroke="#76b900" stroke-width="0.4" opacity="0.35"/><line x1="42" y1="48" x2="118" y2="48" stroke="#76b900" stroke-width="0.4" opacity="0.35"/><line x1="42" y1="62" x2="118" y2="62" stroke="#76b900" stroke-width="0.4" opacity="0.35"/><line x1="68" y1="10" x2="68" y2="86" stroke="#76b900" stroke-width="0.4" opacity="0.35"/><line x1="92" y1="10" x2="92" y2="86" stroke="#76b900" stroke-width="0.4" opacity="0.35"/><text x="80" y="52" text-anchor="middle" fill="#76b900" font-size="11" font-weight="bold" font-family="Arial,sans-serif">NVIDIA</text><circle cx="10" cy="8" r="3" fill="#76b900" opacity="0.5"/><circle cx="150" cy="8" r="3" fill="#76b900" opacity="0.5"/><circle cx="10" cy="88" r="3" fill="#76b900" opacity="0.5"/><circle cx="150" cy="88" r="3" fill="#76b900" opacity="0.5"/></svg>'
SVG["pcie"] = '<svg viewBox="0 0 180 80" xmlns="http://www.w3.org/2000/svg"><rect x="1" y="12" width="168" height="54" rx="3" fill="#07101e" stroke="#1c2e48" stroke-width="1"/><rect x="4" y="15" width="52" height="48" rx="3" fill="#0a1525" stroke="#1c2e48" stroke-width="1"/><circle cx="30" cy="39" r="18" fill="#060e1a" stroke="#1a2a40" stroke-width="1"/><circle cx="30" cy="39" r="13" fill="none" stroke="#76b900" stroke-width="0.6" opacity="0.5"/><circle cx="30" cy="39" r="5" fill="#76b900" opacity="0.85"/><rect x="62" y="20" width="62" height="36" rx="3" fill="#0c1a2e" stroke="#76b900" stroke-width="1.2"/><text x="93" y="41" text-anchor="middle" fill="#76b900" font-size="8" font-weight="bold" font-family="Arial,sans-serif">GPU</text><rect x="130" y="15" width="36" height="48" rx="2" fill="#0a1525" stroke="#1c2e48" stroke-width="0.8"/><line x1="138" y1="22" x2="158" y2="22" stroke="#333" stroke-width="1.5"/><line x1="138" y1="30" x2="158" y2="30" stroke="#333" stroke-width="1.5"/><line x1="138" y1="38" x2="158" y2="38" stroke="#333" stroke-width="1.5"/><rect x="35" y="63" width="90" height="8" rx="1" fill="#111" stroke="#2a2a2a" stroke-width="0.8"/><circle cx="172" cy="25" r="3.5" fill="#76b900" opacity="0.9"/><circle cx="172" cy="38" r="3.5" fill="#ff6600" opacity="0.8"/></svg>'
SVG["workstation"] = '<svg viewBox="0 0 180 90" xmlns="http://www.w3.org/2000/svg"><rect x="1" y="16" width="165" height="60" rx="3" fill="#07101e" stroke="#1c2e48" stroke-width="1"/><rect x="4" y="19" width="100" height="54" rx="3" fill="#0a1525" stroke="#1c2e48" stroke-width="1"/><circle cx="30" cy="46" r="21" fill="#060e1a" stroke="#1a2a40" stroke-width="1"/><circle cx="30" cy="46" r="15" fill="none" stroke="#76b900" stroke-width="0.6" opacity="0.45"/><circle cx="30" cy="46" r="5" fill="#76b900" opacity="0.85"/><circle cx="77" cy="46" r="21" fill="#060e1a" stroke="#1a2a40" stroke-width="1"/><circle cx="77" cy="46" r="15" fill="none" stroke="#76b900" stroke-width="0.6" opacity="0.45"/><circle cx="77" cy="46" r="5" fill="#76b900" opacity="0.85"/><rect x="108" y="22" width="55" height="52" rx="2" fill="#0a1525" stroke="#1c2e48" stroke-width="0.8"/><line x1="118" y1="30" x2="154" y2="30" stroke="#2a3a4a" stroke-width="1.5"/><line x1="118" y1="40" x2="154" y2="40" stroke="#2a3a4a" stroke-width="1.5"/><line x1="118" y1="50" x2="154" y2="50" stroke="#2a3a4a" stroke-width="1.5"/><rect x="30" y="73" width="100" height="8" rx="1" fill="#111" stroke="#2a2a2a" stroke-width="0.8"/><circle cx="170" cy="28" r="3.5" fill="#76b900" opacity="0.9"/><circle cx="170" cy="42" r="3.5" fill="#76b900" opacity="0.9"/></svg>'
SVG["consumer"] = '<svg viewBox="0 0 200 90" xmlns="http://www.w3.org/2000/svg"><rect x="1" y="14" width="184" height="62" rx="3" fill="#07101e" stroke="#1c2e48" stroke-width="1"/><rect x="4" y="17" width="118" height="56" rx="3" fill="#0a1525" stroke="#1c2e48" stroke-width="1"/><circle cx="31" cy="45" r="22" fill="#060e1a" stroke="#1a2a40" stroke-width="1"/><circle cx="31" cy="45" r="15" fill="none" stroke="#76b900" stroke-width="0.6" opacity="0.4"/><circle cx="31" cy="45" r="5" fill="#76b900" opacity="0.85"/><circle cx="83" cy="45" r="22" fill="#060e1a" stroke="#1a2a40" stroke-width="1"/><circle cx="83" cy="45" r="15" fill="none" stroke="#76b900" stroke-width="0.6" opacity="0.4"/><circle cx="83" cy="45" r="5" fill="#76b900" opacity="0.85"/><rect x="126" y="20" width="56" height="52" rx="2" fill="#0a1525" stroke="#1c2e48" stroke-width="0.8"/><line x1="136" y1="30" x2="174" y2="30" stroke="#2a3a4a" stroke-width="1.5"/><line x1="136" y1="40" x2="174" y2="40" stroke="#2a3a4a" stroke-width="1.5"/><line x1="136" y1="50" x2="174" y2="50" stroke="#2a3a4a" stroke-width="1.5"/><line x1="136" y1="60" x2="174" y2="60" stroke="#2a3a4a" stroke-width="1.5"/><rect x="30" y="73" width="110" height="8" rx="1" fill="#111" stroke="#2a2a2a" stroke-width="0.8"/><circle cx="190" cy="25" r="3.5" fill="#ff6600" opacity="0.9"/><circle cx="190" cy="38" r="3.5" fill="#76b900" opacity="0.9"/></svg>'

GB300_RACK_SVG = '<svg viewBox="0 0 220 360" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="rackGrad" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#0d1f35"/><stop offset="100%" stop-color="#070e1a"/></linearGradient><filter id="glow"><feGaussianBlur stdDeviation="3" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs><rect x="8" y="4" width="204" height="352" rx="8" fill="url(#rackGrad)" stroke="#76b900" stroke-width="2"/><rect x="14" y="10" width="192" height="22" rx="4" fill="#0d1f35" stroke="#1e3a5f" stroke-width="0.8"/><text x="110" y="25" text-anchor="middle" fill="#76b900" font-size="9" font-weight="bold" font-family="Arial,sans-serif">NVIDIA GB300 NVL72</text><rect x="14" y="36" width="192" height="18" rx="3" fill="#0c1828" stroke="#76b900" stroke-width="0.8"/><rect x="20" y="39" width="130" height="12" rx="2" fill="#071020" stroke="#1e4070" stroke-width="0.5"/><circle cx="196" cy="45" r="4" fill="#76b900" filter="url(#glow)"/><rect x="14" y="58" width="192" height="18" rx="3" fill="#0c1828" stroke="#76b900" stroke-width="0.8"/><rect x="20" y="61" width="130" height="12" rx="2" fill="#071020" stroke="#1e4070" stroke-width="0.5"/><circle cx="196" cy="67" r="4" fill="#76b900" filter="url(#glow)"/><rect x="14" y="80" width="192" height="18" rx="3" fill="#0c1828" stroke="#76b900" stroke-width="0.8"/><rect x="20" y="83" width="130" height="12" rx="2" fill="#071020" stroke="#1e4070" stroke-width="0.5"/><circle cx="196" cy="89" r="4" fill="#76b900" filter="url(#glow)"/><rect x="14" y="102" width="192" height="18" rx="3" fill="#0c1828" stroke="#76b900" stroke-width="0.8"/><rect x="20" y="105" width="130" height="12" rx="2" fill="#071020" stroke="#1e4070" stroke-width="0.5"/><circle cx="196" cy="111" r="4" fill="#76b900" filter="url(#glow)"/><rect x="14" y="124" width="192" height="18" rx="3" fill="#0c1828" stroke="#76b900" stroke-width="0.8"/><rect x="20" y="127" width="130" height="12" rx="2" fill="#071020" stroke="#1e4070" stroke-width="0.5"/><circle cx="196" cy="133" r="4" fill="#ff6600"/><rect x="14" y="146" width="192" height="18" rx="3" fill="#0c1828" stroke="#76b900" stroke-width="0.8"/><rect x="20" y="149" width="130" height="12" rx="2" fill="#071020" stroke="#1e4070" stroke-width="0.5"/><circle cx="196" cy="155" r="4" fill="#76b900" filter="url(#glow)"/><rect x="14" y="168" width="192" height="18" rx="3" fill="#0c1828" stroke="#76b900" stroke-width="0.8"/><rect x="20" y="171" width="130" height="12" rx="2" fill="#071020" stroke="#1e4070" stroke-width="0.5"/><circle cx="196" cy="177" r="4" fill="#76b900" filter="url(#glow)"/><rect x="14" y="190" width="192" height="18" rx="3" fill="#0c1828" stroke="#76b900" stroke-width="0.8"/><rect x="20" y="193" width="130" height="12" rx="2" fill="#071020" stroke="#1e4070" stroke-width="0.5"/><circle cx="196" cy="199" r="4" fill="#76b900" filter="url(#glow)"/><rect x="14" y="212" width="192" height="40" rx="3" fill="#0a1520" stroke="#1e3a5f" stroke-width="0.8"/><text x="110" y="228" text-anchor="middle" fill="#76b900" font-size="8" font-family="Arial,sans-serif">NVLink Switch Module</text><text x="110" y="244" text-anchor="middle" fill="#1e5090" font-size="7" font-family="Arial,sans-serif">900 GB/s bidirectional</text><rect x="14" y="256" width="192" height="18" rx="3" fill="#0c1828" stroke="#76b900" stroke-width="0.8"/><rect x="20" y="259" width="130" height="12" rx="2" fill="#071020" stroke="#1e4070" stroke-width="0.5"/><circle cx="196" cy="265" r="4" fill="#76b900" filter="url(#glow)"/><rect x="14" y="278" width="192" height="18" rx="3" fill="#0c1828" stroke="#76b900" stroke-width="0.8"/><rect x="20" y="281" width="130" height="12" rx="2" fill="#071020" stroke="#1e4070" stroke-width="0.5"/><circle cx="196" cy="287" r="4" fill="#76b900" filter="url(#glow)"/><rect x="14" y="300" width="192" height="30" rx="3" fill="#0a1520" stroke="#1e3a5f" stroke-width="0.8"/><text x="110" y="319" text-anchor="middle" fill="#5aadff" font-size="7" font-family="Arial,sans-serif">Power Supply Units</text><rect x="14" y="334" width="192" height="16" rx="3" fill="#0d1f35" stroke="#1e3a5f" stroke-width="0.5"/><text x="110" y="346" text-anchor="middle" fill="#8890a8" font-size="7" font-family="Arial,sans-serif">72x GPU · 13,824 GB · 120 kW</text></svg>'

CLUSTER_SVG = '<svg viewBox="0 0 480 200" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:480px"><defs><marker id="arr" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto"><polygon points="0 0, 6 3, 0 6" fill="#76b900" opacity="0.7"/></marker></defs><rect x="200" y="80" width="80" height="40" rx="5" fill="#0c1a2e" stroke="#76b900" stroke-width="1.5"/><text x="240" y="104" text-anchor="middle" fill="#76b900" font-size="9" font-family="Arial,sans-serif" font-weight="bold">SWITCH</text><rect x="20" y="30" width="110" height="60" rx="5" fill="#0d1525" stroke="#2a4a7a" stroke-width="1"/><rect x="28" y="40" width="90" height="10" rx="2" fill="#0c1f35" stroke="#76b900" stroke-width="0.5"/><rect x="28" y="55" width="90" height="10" rx="2" fill="#0c1f35" stroke="#76b900" stroke-width="0.5"/><text x="73" y="90" text-anchor="middle" fill="#8890a8" font-size="8" font-family="Arial,sans-serif">Server 1 · 8× H100</text><circle cx="118" cy="40" r="4" fill="#76b900"/><line x1="130" y1="60" x2="200" y2="100" stroke="#76b900" stroke-width="1" opacity="0.6" marker-end="url(#arr)"/><rect x="20" y="120" width="110" height="60" rx="5" fill="#0d1525" stroke="#2a4a7a" stroke-width="1"/><rect x="28" y="130" width="90" height="10" rx="2" fill="#0c1f35" stroke="#76b900" stroke-width="0.5"/><rect x="28" y="145" width="90" height="10" rx="2" fill="#0c1f35" stroke="#76b900" stroke-width="0.5"/><text x="73" y="192" text-anchor="middle" fill="#8890a8" font-size="8" font-family="Arial,sans-serif">Server 2 · 8× H100</text><circle cx="118" cy="130" r="4" fill="#76b900"/><line x1="130" y1="150" x2="200" y2="100" stroke="#76b900" stroke-width="1" opacity="0.6" marker-end="url(#arr)"/><rect x="350" y="30" width="110" height="60" rx="5" fill="#0d1525" stroke="#2a4a7a" stroke-width="1"/><rect x="358" y="40" width="90" height="10" rx="2" fill="#0c1f35" stroke="#76b900" stroke-width="0.5"/><rect x="358" y="55" width="90" height="10" rx="2" fill="#0c1f35" stroke="#76b900" stroke-width="0.5"/><text x="405" y="90" text-anchor="middle" fill="#8890a8" font-size="8" font-family="Arial,sans-serif">Server 3 · 8× H100</text><circle cx="358" cy="40" r="4" fill="#76b900"/><line x1="350" y1="60" x2="280" y2="100" stroke="#76b900" stroke-width="1" opacity="0.6" marker-end="url(#arr)"/><rect x="350" y="120" width="110" height="60" rx="5" fill="#0d1525" stroke="#2a4a7a" stroke-width="1"/><rect x="358" y="130" width="90" height="10" rx="2" fill="#0c1f35" stroke="#76b900" stroke-width="0.5"/><rect x="358" y="145" width="90" height="10" rx="2" fill="#0c1f35" stroke="#76b900" stroke-width="0.5"/><text x="405" y="192" text-anchor="middle" fill="#8890a8" font-size="8" font-family="Arial,sans-serif">Server 4 · 8× H100</text><circle cx="358" cy="130" r="4" fill="#76b900"/><line x1="350" y1="150" x2="280" y2="100" stroke="#76b900" stroke-width="1" opacity="0.6" marker-end="url(#arr)"/></svg>'

HERO_SVG = '<svg viewBox="0 0 360 280" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:360px;opacity:0.92"><ellipse cx="180" cy="140" rx="160" ry="120" fill="#76b900" opacity="0.03"/><rect x="30" y="40" width="70" height="160" rx="6" fill="#0a1020" stroke="#76b900" stroke-width="1.2"/><rect x="36" y="52" width="58" height="12" rx="2" fill="#0c1f35" stroke="#76b900" stroke-width="0.6"/><rect x="36" y="70" width="58" height="12" rx="2" fill="#0c1f35" stroke="#76b900" stroke-width="0.6"/><rect x="36" y="88" width="58" height="12" rx="2" fill="#0c1f35" stroke="#76b900" stroke-width="0.6"/><rect x="36" y="106" width="58" height="12" rx="2" fill="#0c1f35" stroke="#76b900" stroke-width="0.6"/><rect x="36" y="124" width="58" height="12" rx="2" fill="#0c1f35" stroke="#1e4070" stroke-width="0.6"/><circle cx="86" cy="58" r="3" fill="#76b900" opacity="0.9"/><circle cx="86" cy="76" r="3" fill="#76b900" opacity="0.9"/><circle cx="86" cy="94" r="3" fill="#ff6600" opacity="0.8"/><circle cx="86" cy="112" r="3" fill="#76b900" opacity="0.9"/><rect x="145" y="20" width="70" height="200" rx="6" fill="#0a1020" stroke="#76b900" stroke-width="1.8"/><rect x="151" y="34" width="58" height="12" rx="2" fill="#0c1f35" stroke="#76b900" stroke-width="0.8"/><rect x="151" y="52" width="58" height="12" rx="2" fill="#0c1f35" stroke="#76b900" stroke-width="0.8"/><rect x="151" y="70" width="58" height="12" rx="2" fill="#0c1f35" stroke="#76b900" stroke-width="0.8"/><rect x="151" y="88" width="58" height="12" rx="2" fill="#0c1f35" stroke="#76b900" stroke-width="0.8"/><rect x="151" y="106" width="58" height="12" rx="2" fill="#0c1f35" stroke="#76b900" stroke-width="0.8"/><rect x="151" y="124" width="58" height="12" rx="2" fill="#0c1f35" stroke="#76b900" stroke-width="0.8"/><circle cx="201" cy="40" r="3.5" fill="#76b900"/><circle cx="201" cy="58" r="3.5" fill="#76b900"/><circle cx="201" cy="76" r="3.5" fill="#76b900"/><circle cx="201" cy="94" r="3.5" fill="#76b900"/><circle cx="201" cy="112" r="3.5" fill="#ff6600" opacity="0.8"/><rect x="260" y="40" width="70" height="160" rx="6" fill="#0a1020" stroke="#76b900" stroke-width="1.2"/><rect x="266" y="52" width="58" height="12" rx="2" fill="#0c1f35" stroke="#76b900" stroke-width="0.6"/><rect x="266" y="70" width="58" height="12" rx="2" fill="#0c1f35" stroke="#76b900" stroke-width="0.6"/><rect x="266" y="88" width="58" height="12" rx="2" fill="#0c1f35" stroke="#76b900" stroke-width="0.6"/><rect x="266" y="106" width="58" height="12" rx="2" fill="#0c1f35" stroke="#76b900" stroke-width="0.6"/><circle cx="316" cy="58" r="3" fill="#76b900" opacity="0.9"/><circle cx="316" cy="76" r="3" fill="#76b900" opacity="0.9"/><circle cx="316" cy="94" r="3" fill="#76b900" opacity="0.9"/><circle cx="316" cy="112" r="3" fill="#ff6600" opacity="0.8"/><line x1="100" y1="120" x2="145" y2="120" stroke="#76b900" stroke-width="1" opacity="0.45" stroke-dasharray="4 3"/><line x1="215" y1="120" x2="260" y2="120" stroke="#76b900" stroke-width="1" opacity="0.45" stroke-dasharray="4 3"/><text x="180" y="260" text-anchor="middle" fill="#76b900" font-size="11" font-family="Arial,sans-serif" font-weight="bold">AI Cluster · NVLink + InfiniBand</text></svg>'

HTML_BASE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Maria's AI Hardware Store</title>
<style>
:root {
  --bg:#fafbfc; --bg2:#f2f4f7; --bg3:#eef1f5; --card:#ffffff;
  --border:#e5e8ee; --border2:#d5d9e2; --accent:#3f6b00; --accent2:#5c9400;
  --accent-fill:#6fae00; --text:#262b36; --muted:#5b6170; --white:#0a0d12;
  --radius-sm:10px; --radius-md:14px; --radius-lg:18px; --radius-xl:24px;
  --shadow-sm:0 1px 2px rgba(16,24,40,.04),0 2px 8px rgba(16,24,40,.06);
  --shadow-md:0 2px 4px rgba(16,24,40,.04),0 12px 28px rgba(16,24,40,.08);
  --shadow-lg:0 4px 6px rgba(16,24,40,.03),0 20px 40px rgba(16,24,40,.10);
  --ease:cubic-bezier(.16,1,.3,1);
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;background:var(--bg);color:var(--text);line-height:1.65;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}

/* ANNOUNCEMENT BAR */
.announce{background:var(--white);color:#e8eaf0;text-align:center;padding:9px 20px;font-size:.82em;font-weight:500;letter-spacing:.01em}
.announce a{color:#fff;text-decoration:none;font-weight:700;margin-left:6px}
.announce a:hover{text-decoration:underline}
.announce .pill{display:inline-block;background:var(--accent-fill);color:#0c1400;font-weight:800;font-size:.78em;letter-spacing:.04em;padding:2px 9px;border-radius:20px;margin-right:9px;vertical-align:1px}

/* HEADER — single unified bar: logo, nav, search, icons, CTA */
header{background:rgba(255,255,255,.92);-webkit-backdrop-filter:blur(14px) saturate(1.2);backdrop-filter:blur(14px) saturate(1.2);border-bottom:1px solid var(--border);padding:14px 40px;display:flex;align-items:center;gap:30px;position:sticky;top:0;z-index:200}
.brand-logo{display:flex;align-items:center;gap:9px;font-size:1.12em;font-weight:800;color:var(--white);letter-spacing:-.01em;text-decoration:none;white-space:nowrap;flex-shrink:0}
.brand-logo .mark{display:inline-flex;align-items:center;justify-content:center;width:29px;height:29px;border-radius:8px;background:var(--accent-fill);font-size:.82em;flex-shrink:0}
.hdr-nav{display:flex;align-items:center;gap:22px;flex-shrink:0}
.hdr-nav a{color:var(--muted);text-decoration:none;font-size:.87em;font-weight:500;white-space:nowrap;transition:color .2s}
.hdr-nav a:hover{color:var(--white)}
.hdr-search{flex:1;max-width:340px;position:relative}
.hdr-search input{width:100%;padding:9px 14px 9px 36px;background:var(--bg2);border:1px solid var(--border);border-radius:100px;font-size:.85em;color:var(--text);font-family:inherit;transition:border-color .2s,background .2s}
.hdr-search input:focus{outline:none;border-color:var(--border2);background:var(--card)}
.hdr-search .si{position:absolute;left:13px;top:50%;transform:translateY(-50%);color:var(--muted);font-size:.9em;pointer-events:none}
.hdr-actions{display:flex;align-items:center;gap:10px;margin-left:auto;flex-shrink:0}
.hdr-icon-btn{display:flex;align-items:center;justify-content:center;width:36px;height:36px;border-radius:50%;background:var(--bg2);border:1px solid var(--border);color:var(--text);text-decoration:none;transition:border-color .2s,background .2s}
.hdr-icon-btn:hover{border-color:var(--border2);background:var(--bg3)}
.hdr-cta{display:inline-flex;align-items:center;gap:8px;background:var(--white);color:#fff;text-decoration:none;padding:10px 22px;border-radius:100px;font-weight:700;font-size:.86em;letter-spacing:.01em;transition:transform .2s var(--ease),box-shadow .2s var(--ease),background .2s;white-space:nowrap}
.hdr-cta:hover{background:#000;transform:translateY(-1px);box-shadow:var(--shadow-md)}

/* LAYOUT */
main{max-width:1240px;margin:0 auto;padding:0 24px 130px}
section{margin-bottom:clamp(64px,9vw,104px)}
.sec-label{font-size:.76em;font-weight:700;color:var(--accent);letter-spacing:.14em;text-transform:uppercase;margin-bottom:10px}
.sec-title{font-size:clamp(1.4em,2.2vw,1.9em);font-weight:800;letter-spacing:-.01em;color:var(--white);margin-bottom:10px;line-height:1.2}
.sec-sub{color:var(--muted);font-size:1em;max-width:640px;margin-bottom:36px;line-height:1.6}

/* ANIMATIONS */
@keyframes fadeInUp{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:translateY(0)}}
.fade-in{opacity:0;transform:translateY(18px);transition:opacity .7s var(--ease),transform .7s var(--ease)}
.fade-in.visible{opacity:1;transform:translateY(0)}
.hero .fade-in{animation:fadeInUp .8s var(--ease) forwards}

/* HERO */
.hero{padding:clamp(48px,7vw,76px) 0 clamp(36px,5vw,48px);display:grid;grid-template-columns:.85fr 1.15fr;gap:44px;align-items:center}
.hero-badge{display:inline-block;background:rgba(111,174,0,.09);border:1px solid rgba(111,174,0,.3);color:var(--accent);padding:6px 15px;border-radius:20px;font-size:.79em;font-weight:600;margin-bottom:22px;letter-spacing:.03em}
.hero-title{font-size:clamp(2.2rem,1.1rem + 4.4vw,4.1rem);font-weight:800;line-height:1.02;letter-spacing:-.03em;color:var(--white);margin-bottom:20px}
.hero-title span{color:var(--accent)}
.hero-sub{font-size:.96em;color:var(--accent);font-weight:600;margin-bottom:17px;opacity:.9}
.hero-msg{font-size:1.14em;color:var(--muted);max-width:460px;margin-bottom:34px;line-height:1.6}
.hero-btns{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:38px}
.btn-primary{display:inline-flex;align-items:center;gap:8px;background:var(--white);color:#fff;text-decoration:none;padding:15px 28px;border-radius:100px;font-weight:700;font-size:.95em;transition:transform .2s var(--ease),box-shadow .2s var(--ease),background .2s}
.btn-primary:hover{background:#000;transform:translateY(-2px);box-shadow:var(--shadow-md)}
.btn-ghost{display:inline-flex;align-items:center;gap:8px;background:var(--card);color:var(--text);text-decoration:none;padding:15px 28px;border-radius:100px;font-weight:600;font-size:.95em;border:1px solid var(--border2);transition:border-color .2s,color .2s,transform .2s var(--ease),background .2s}
.btn-ghost:hover{border-color:var(--white);color:var(--white);transform:translateY(-2px)}
.trust-strip{display:flex;flex-wrap:wrap;gap:26px}
.trust-strip .ti{display:flex;align-items:center;gap:9px}
.trust-strip .ti-icon{color:var(--accent);font-size:1.05em;flex-shrink:0}
.trust-strip .ti-name{font-size:.83em;font-weight:700;color:var(--white);line-height:1.3}
.trust-strip .ti-sub{font-size:.74em;color:var(--muted);line-height:1.3}
.hero-visual{position:relative;min-height:550px;border-radius:var(--radius-xl);overflow:hidden;background:#111}
.hero-visual img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:block}
.hero3d-metric{position:absolute;right:22px;top:26px;z-index:4;background:rgba(18,20,24,.86);-webkit-backdrop-filter:blur(16px) saturate(1.3);backdrop-filter:blur(16px) saturate(1.3);border:1px solid rgba(255,255,255,.08);border-radius:var(--radius-lg);padding:18px 22px;box-shadow:0 20px 40px rgba(0,0,0,.25);color:#fff;min-width:190px;transition:transform .3s var(--ease),box-shadow .3s var(--ease)}
.hero3d-metric:hover{transform:translateY(-3px);box-shadow:0 26px 50px rgba(0,0,0,.32)}
.hero3d-metric .m-eyebrow{display:flex;align-items:center;gap:6px;font-size:.68em;letter-spacing:.1em;text-transform:uppercase;color:#8f96a3;font-weight:700;margin-bottom:10px}
.hero3d-metric-num{font-size:1.9em;font-weight:800;line-height:1.1;font-variant-numeric:tabular-nums;color:#fff}
.hero3d-metric-num small{font-size:.5em;font-weight:600;color:#9aa0ac;margin-left:3px}
.hero3d-metric-lbl{font-size:.78em;color:#9aa0ac;margin-top:2px;margin-bottom:14px;letter-spacing:.01em}
.hero3d-metric .m-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;border-top:1px solid rgba(255,255,255,.08);padding-top:14px}
.hero3d-metric .m-val{font-size:1.05em;font-weight:700;color:#fff;font-variant-numeric:tabular-nums}
.hero3d-metric .m-lbl{font-size:.7em;color:#8f96a3;margin-top:1px}
.hero3d-metric-num{font-size:1.9em;font-weight:800;color:var(--accent);line-height:1.1;font-variant-numeric:tabular-nums}
.hero3d-metric-lbl{font-size:.78em;color:var(--muted);margin-top:4px;letter-spacing:.02em}

/* STATS BAR */
.stat-lbl{font-size:.78em;color:var(--muted);margin-top:6px;letter-spacing:.02em}

/* BUILD YOUR AI CLUSTER — interactive calculator */
.calc-card{background:var(--white);border-radius:var(--radius-xl);padding:clamp(32px,4vw,48px);display:grid;grid-template-columns:.85fr 1.15fr;gap:44px;color:#fff;box-shadow:0 30px 70px rgba(0,0,0,.28);border:1px solid rgba(255,255,255,.06)}
.calc-intro{display:flex;align-items:center;gap:12px;margin-bottom:8px;flex-wrap:wrap}
.calc-intro h3{font-size:1.55em;font-weight:800;letter-spacing:-.015em}
.calc-tag{font-size:.68em;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--accent-fill);background:rgba(111,174,0,.16);border:1px solid rgba(111,174,0,.32);padding:3px 10px;border-radius:20px}
.calc-desc{color:#9aa0ac;font-size:.94em;line-height:1.65;margin-bottom:26px;max-width:360px}
.calc-field{margin-bottom:16px}
.calc-field label{display:block;font-size:.78em;color:#9aa0ac;margin-bottom:7px;font-weight:500}
.calc-field select{width:100%;padding:12px 14px;background:#1c1e24;border:1px solid #33363e;border-radius:var(--radius-sm);color:#fff;font-size:.92em;font-family:inherit;cursor:pointer;transition:border-color .2s}
.calc-field select:hover{border-color:#454952}
.calc-field select:focus{outline:none;border-color:var(--accent-fill)}
.calc-results{background:#0e1013;border-radius:var(--radius-lg);padding:26px;display:flex;flex-direction:column;gap:20px;border:1px solid rgba(255,255,255,.04)}
.calc-row{display:grid;grid-template-columns:repeat(4,1fr);gap:18px}
.calc-stat .cs-lbl{font-size:.72em;color:#8f96a3;margin-bottom:5px}
.calc-stat .cs-val{font-size:1.42em;font-weight:800;color:#fff;font-variant-numeric:tabular-nums;line-height:1.15}
.calc-stat .cs-sub{font-size:.72em;color:#8f96a3;margin-top:2px}
.calc-cta-row{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;border-top:1px solid #23262d;padding-top:18px}
.calc-cta{display:inline-flex;align-items:center;gap:8px;background:var(--accent-fill);color:#0c1400;text-decoration:none;padding:13px 24px;border-radius:100px;font-weight:700;font-size:.92em;transition:background .2s,transform .2s var(--ease),box-shadow .2s var(--ease)}
.calc-cta:hover{background:var(--accent2);transform:translateY(-2px);box-shadow:0 12px 28px rgba(111,174,0,.28)}
.calc-note{font-size:.76em;color:#767c88}

/* FEATURED HARDWARE — carousel */
.carousel-head{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:24px;flex-wrap:wrap;gap:10px}
.carousel-head .view-all{font-size:.86em;font-weight:700;color:var(--accent);text-decoration:none}
.carousel-head .view-all:hover{text-decoration:underline}
.carousel-wrap{position:relative}
.carousel-track{display:flex;gap:20px;overflow-x:auto;scroll-snap-type:x mandatory;padding:4px 4px 12px;scrollbar-width:none}
.carousel-track::-webkit-scrollbar{display:none}
.pcard{scroll-snap-align:start;flex:0 0 auto;width:300px;background:#101114;border-radius:var(--radius-lg);padding:22px;position:relative;box-shadow:0 1px 2px rgba(0,0,0,.2);transition:transform .35s var(--ease),box-shadow .35s var(--ease)}
.pcard:hover{transform:translateY(-6px);box-shadow:0 24px 48px rgba(0,0,0,.35)}
.pcard .pcard-badge{position:absolute;top:16px;left:16px;background:var(--accent-fill);color:#0c1400;font-size:.68em;font-weight:800;padding:3px 9px;border-radius:20px;letter-spacing:.02em}
.pcard-img{height:180px;display:flex;align-items:center;justify-content:center;margin-bottom:16px;transition:transform .35s var(--ease)}
.pcard:hover .pcard-img{transform:scale(1.04)}
.pcard-img svg{max-width:92%;max-height:92%}
.pcard h4{color:#fff;font-size:1.08em;font-weight:700;margin-bottom:4px;letter-spacing:-.005em}
.pcard .pcard-spec{color:#8f96a3;font-size:.79em;margin-bottom:12px}
.pcard .pcard-price{color:var(--accent-fill);font-size:1.22em;font-weight:800;font-variant-numeric:tabular-nums}
.carousel-nav{display:flex;align-items:center;justify-content:center;width:42px;height:42px;border-radius:50%;background:var(--card);border:1px solid var(--border);color:var(--text);cursor:pointer;transition:border-color .2s,background .2s,transform .2s var(--ease);flex-shrink:0}
.carousel-nav:hover{border-color:var(--border2);background:var(--bg2);transform:translateY(-1px)}
.carousel-nav:disabled{opacity:.35;cursor:default;transform:none}
.carousel-controls{display:flex;align-items:center;justify-content:center;gap:16px;margin-top:18px}
.carousel-dots{display:flex;gap:7px}
.carousel-dots span{width:6px;height:6px;border-radius:50%;background:var(--border2);transition:background .2s,transform .2s}
.carousel-dots span.active{background:var(--accent);transform:scale(1.3)}

/* BOTTOM FEATURE STRIP (dark) */
.feature-strip{background:var(--white);border-radius:var(--radius-xl);padding:clamp(28px,3.5vw,36px);display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:28px}
.feature-strip .fs-item{display:flex;align-items:flex-start;gap:13px}
.feature-strip .fs-icon{color:var(--accent-fill);flex-shrink:0;font-size:1.3em;line-height:1}
.feature-strip h4{color:#fff;font-size:.92em;font-weight:700;margin-bottom:3px}
.feature-strip p{color:#9aa0ac;font-size:.8em;line-height:1.5}

/* FEATURED */
.featured-wrap{background:var(--card);border:1px solid var(--border);border-top:3px solid var(--accent-fill);border-radius:var(--radius-xl);padding:clamp(28px,4vw,44px);display:grid;grid-template-columns:260px 1fr;gap:48px;align-items:center;position:relative;overflow:hidden;box-shadow:var(--shadow-md)}
.featured-wrap::before{content:"";position:absolute;top:-60px;right:-60px;width:320px;height:320px;background:radial-gradient(circle,rgba(111,174,0,.05) 0%,transparent 70%);pointer-events:none}
.fe-rack{display:flex;justify-content:center}
.fe-rack svg{filter:drop-shadow(0 6px 20px rgba(16,24,40,.18))}
.fe-badge{display:inline-flex;align-items:center;gap:7px;background:rgba(111,174,0,.10);border:1px solid rgba(111,174,0,.32);color:var(--accent);padding:5px 14px;border-radius:20px;font-size:.76em;font-weight:700;margin-bottom:16px;letter-spacing:.06em}
.fe-title{font-size:clamp(1.6em,2.6vw,2.1em);font-weight:800;letter-spacing:-.01em;color:var(--white);margin-bottom:8px}
.fe-sub{color:var(--accent);font-size:.92em;font-weight:600;margin-bottom:16px}
.fe-desc{color:var(--muted);font-size:.92em;max-width:540px;margin-bottom:22px;line-height:1.65}
.fe-specs{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:24px}
.fe-spec{background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius-sm);padding:9px 17px;text-align:center}
.fe-spec-val{font-size:1.05em;font-weight:700;color:var(--accent);font-variant-numeric:tabular-nums}
.fe-spec-lbl{font-size:.72em;color:var(--muted);margin-top:3px;letter-spacing:.02em}
.fe-cases{color:var(--muted);font-size:.87em;margin-bottom:24px;line-height:1.7}
.fe-cases li{margin:4px 0 4px 16px}

/* BADGE STYLES */
.bdg{display:inline-block;padding:4px 12px;border-radius:20px;font-size:.72em;font-weight:700;letter-spacing:.05em;margin-bottom:12px}
.bdg-frontier{background:rgba(150,100,255,.10);color:#6d28d9;border:1px solid rgba(150,100,255,.35)}
.bdg-popular{background:rgba(255,120,30,.10);color:#b45309;border:1px solid rgba(255,120,30,.35)}
.bdg-enterprise{background:rgba(111,174,0,.10);color:var(--accent);border:1px solid rgba(111,174,0,.35)}
.bdg-value{background:rgba(255,210,50,.16);color:#a16207;border:1px solid rgba(210,160,20,.35)}
.bdg-workstation{background:rgba(37,99,235,.09);color:#2563eb;border:1px solid rgba(37,99,235,.3)}
.bdg-budget{background:rgba(120,120,130,.10);color:#52525b;border:1px solid rgba(120,120,130,.3)}

/* GPU CARDS */
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:22px}
.gpu-card{background:var(--card);border:1px solid var(--border);border-top:3px solid transparent;border-radius:var(--radius-lg);padding:24px;transition:border-top-color .25s var(--ease),transform .25s var(--ease),box-shadow .25s var(--ease);display:flex;flex-direction:column}
.gpu-card:hover{border-top-color:var(--accent-fill);transform:translateY(-4px);box-shadow:var(--shadow-lg)}
.gpu-icon{border-radius:var(--radius-sm);overflow:hidden;margin-bottom:16px;background:#08101e}
.gpu-icon svg{display:block;width:100%;height:auto}
.gpu-price{font-size:1.6em;font-weight:800;color:var(--accent);margin:10px 0;font-variant-numeric:tabular-nums;letter-spacing:-.01em}
.spec-row{display:flex;align-items:center;gap:7px;font-size:.83em;color:var(--muted);margin:4px 0}
.spec-row strong{color:var(--text);font-weight:600}
.spec-row .spec-icon{font-size:.95em;min-width:18px}
.spec-divider{border:none;border-top:1px solid var(--border);margin:12px 0}
.card-actions{margin-top:auto;padding-top:16px}

/* HOW TO CHOOSE */
.htc-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:18px}
.htc-card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius-lg);padding:24px;display:flex;flex-direction:column;gap:10px;transition:border-color .25s var(--ease),transform .25s var(--ease),box-shadow .25s var(--ease)}
.htc-card:hover{border-color:var(--accent-fill);transform:translateY(-3px);box-shadow:var(--shadow-sm)}
.htc-vram{font-size:.8em;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.08em}
.htc-arrow{font-size:1.3em;color:var(--accent)}
.htc-gpu{font-size:1.1em;font-weight:700;color:var(--white)}
.htc-price{font-size:1.3em;font-weight:800;color:var(--accent);font-variant-numeric:tabular-nums}
.htc-note{font-size:.83em;color:var(--muted);line-height:1.55}

/* SIZING (compact, below hero) */
.sizing-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:16px}
.sizing-step{display:flex;gap:13px;align-items:flex-start;background:var(--card);border:1px solid var(--border);border-radius:var(--radius-md);padding:18px;transition:border-color .2s}
.sizing-step:hover{border-color:var(--border2)}
.sizing-num{background:var(--accent-fill);color:#0c1400;font-weight:800;width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:.85em}
.sizing-step strong{color:var(--white);font-size:.92em;letter-spacing:-.005em}
.sizing-step p{color:var(--muted);font-size:.83em;margin-top:4px;line-height:1.5}
.sizing-example{background:var(--bg3);border-left:3px solid var(--accent-fill);border-radius:0 var(--radius-sm) var(--radius-sm) 0;padding:14px 20px;color:var(--text);font-size:.89em;line-height:1.6}

/* COMPARE TABLE */
.tbl-wrap{overflow-x:auto;border-radius:var(--radius-md);border:1px solid var(--border)}
table{width:100%;border-collapse:collapse;background:var(--card)}
th{background:var(--bg3);color:var(--accent);padding:14px 20px;text-align:left;font-size:.78em;font-weight:700;letter-spacing:.08em;text-transform:uppercase;border-bottom:1px solid var(--border)}
td{padding:14px 20px;border-bottom:1px solid var(--border);font-size:.9em;color:var(--text)}
tr:last-child td{border-bottom:none}
tbody tr{transition:background .15s}
tbody tr:hover td{background:rgba(111,174,0,.05)}
.td-name{font-weight:600;color:var(--white)}
.td-mem{color:var(--accent);font-weight:600;font-variant-numeric:tabular-nums}
.hyper td{color:var(--accent)}

/* MODELS */
.model-card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius-lg);padding:24px;margin-bottom:14px;transition:border-color .2s,box-shadow .2s var(--ease)}
.model-card:hover{border-color:var(--border2);box-shadow:var(--shadow-md)}
.mem-calc{background:var(--bg3);border-left:3px solid var(--accent-fill);padding:15px 19px;border-radius:0 var(--radius-sm) var(--radius-sm) 0;font-family:'Courier New',monospace;font-size:.85em;margin-top:16px;line-height:1.85}
.mem-result{color:var(--accent);font-weight:700}

/* CLUSTER */
.cluster-section{display:grid;grid-template-columns:1fr 1fr;gap:44px;align-items:start}
.cluster-diagram{background:linear-gradient(160deg,#0d1420,#080b12);border:1px solid var(--border);border-radius:var(--radius-lg);padding:28px;box-shadow:var(--shadow-sm)}
.explainer-box{background:var(--card);border:1px solid var(--border);border-radius:var(--radius-md);padding:18px;margin-bottom:12px;transition:border-color .2s}
.explainer-box:hover{border-color:var(--border2)}
.explainer-box h4{color:var(--accent);margin-bottom:7px;font-size:.9em;font-weight:700}
.explainer-box p{font-size:.86em;color:var(--muted);line-height:1.6}

/* BUILDS */
.build-card{background:var(--card);border:1px solid var(--border);border-left:4px solid var(--accent-fill);border-radius:var(--radius-lg);padding:28px;margin-bottom:20px;transition:box-shadow .25s var(--ease),transform .25s var(--ease)}
.build-card:hover{box-shadow:var(--shadow-md);transform:translateY(-2px)}
.bld-stats{display:grid;grid-template-columns:repeat(auto-fill,minmax(155px,1fr));gap:12px;margin:18px 0}
.stat-box{background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius-sm);padding:14px;text-align:center}
.stat-val{font-size:1.28em;font-weight:800;color:var(--accent);font-variant-numeric:tabular-nums}
.pwr-row{display:flex;gap:12px;flex-wrap:wrap;margin-top:16px}
.pwr-box{background:rgba(111,174,0,.06);border:1px solid rgba(111,174,0,.2);border-radius:var(--radius-sm);padding:13px 17px;font-size:.87em;display:flex;align-items:center;gap:11px}
.pwr-icon{font-size:1.4em;line-height:1}
.path-pill{display:inline-block;padding:4px 13px;border-radius:20px;font-size:.78em;font-weight:700;letter-spacing:.03em;margin-bottom:12px}
.pill-startup{background:rgba(255,102,0,.10);color:#b45309;border:1px solid rgba(255,102,0,.32)}
.pill-mid{background:rgba(37,99,235,.09);color:#2563eb;border:1px solid rgba(37,99,235,.3)}
.pill-ent{background:rgba(111,174,0,.10);color:var(--accent);border:1px solid rgba(111,174,0,.32)}

/* TRUST */
.trust-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px}
.trust-item{display:flex;align-items:flex-start;gap:15px;background:var(--card);border:1px solid var(--border);border-radius:var(--radius-md);padding:20px;transition:border-color .2s}
.trust-item:hover{border-color:var(--border2)}
.trust-check{flex-shrink:0;width:28px;height:28px;background:rgba(111,174,0,.10);border:1px solid rgba(111,174,0,.32);border-radius:50%;display:flex;align-items:center;justify-content:center;color:var(--accent);font-size:.85em;font-weight:700}
.trust-item h4{color:var(--white);font-size:.93em;margin-bottom:4px;font-weight:700}
.trust-item p{color:var(--muted);font-size:.83em;line-height:1.55}

/* WHY */
.why-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:16px}
.why-card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius-md);padding:22px;transition:border-color .2s,transform .2s var(--ease)}
.why-card:hover{border-color:var(--border2);transform:translateY(-2px)}
.why-icon{font-size:1.7em;margin-bottom:12px}
.why-card h4{color:var(--white);margin-bottom:6px;font-size:.94em;font-weight:700}
.why-card p{color:var(--muted);font-size:.83em;line-height:1.55}

/* ABOUT */
.about-grid{display:grid;grid-template-columns:auto 1fr;gap:40px;align-items:center;background:var(--card);border:1px solid var(--border);border-radius:var(--radius-xl);padding:40px;box-shadow:var(--shadow-md)}
.about-avatar{width:110px;height:110px;border-radius:50%;background:radial-gradient(circle at 35% 30%,rgba(111,174,0,.16),rgba(111,174,0,.05));border:2px solid rgba(111,174,0,.3);display:flex;align-items:center;justify-content:center;font-size:3em;flex-shrink:0}
.about-content h2{color:var(--white);font-size:clamp(1.4em,2.2vw,1.7em);font-weight:800;letter-spacing:-.01em;margin-bottom:14px}
.about-content p{color:var(--muted);font-size:.92em;line-height:1.7;margin-bottom:16px}
.about-contacts{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:22px}
.about-contact-item{background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius-sm);padding:11px 17px;font-size:.86em}
.about-contact-item .aci-lbl{color:var(--muted);font-size:.76em}
.about-contact-item .aci-val{color:var(--white);font-weight:600}
.about-btns{display:flex;gap:12px;flex-wrap:wrap}

/* CONTACT */
.contact-grid{display:grid;grid-template-columns:1fr 1fr;gap:22px}
.contact-card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius-lg);padding:32px}
.contact-intro{color:var(--muted);margin-bottom:24px;line-height:1.7;font-size:.92em}
.contact-line{display:flex;align-items:center;gap:14px;background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius-sm);padding:14px 18px;margin-bottom:11px}
.ci-icon{font-size:1.25em}
.ci-lbl{font-size:.75em;color:var(--muted)}
.ci-val{font-weight:600;color:var(--white);font-size:.94em}
.ci-val a{color:var(--accent);text-decoration:none}
.ci-val a:hover{text-decoration:underline}
.contact-btns{display:flex;gap:11px;flex-wrap:wrap;margin-top:20px}
.btn-wa{display:inline-flex;align-items:center;gap:8px;background:#25D366;border:1px solid #25D366;color:#fff;text-decoration:none;padding:11px 21px;border-radius:var(--radius-sm);font-weight:700;font-size:.88em;transition:background .2s,transform .2s var(--ease),box-shadow .2s;box-shadow:var(--shadow-sm)}
.btn-wa:hover{background:#1ebe5d;transform:translateY(-1px);box-shadow:var(--shadow-md)}
.btn-email{display:inline-flex;align-items:center;gap:8px;background:var(--bg3);border:1px solid var(--border2);color:var(--text);text-decoration:none;padding:11px 21px;border-radius:var(--radius-sm);font-weight:600;font-size:.88em;transition:border-color .2s,color .2s,transform .2s var(--ease)}
.btn-email:hover{border-color:var(--accent);color:var(--accent);transform:translateY(-1px)}

/* FORM */
.form-wrap{background:var(--card);border:1px solid var(--border);border-radius:var(--radius-lg);padding:32px;max-width:600px}
.form-wrap label{display:block;font-size:.84em;color:var(--muted);margin-bottom:7px;margin-top:20px;font-weight:500}
.form-wrap label:first-child{margin-top:0}
.form-wrap input,.form-wrap select{width:100%;padding:12px 16px;background:var(--bg3);border:1px solid var(--border2);border-radius:var(--radius-sm);color:var(--text);font-size:.94em;font-family:inherit;transition:border-color .2s,box-shadow .2s}
.form-wrap input:focus,.form-wrap select:focus{outline:none;border-color:var(--accent-fill);box-shadow:0 0 0 3px rgba(111,174,0,.16)}
.form-wrap button{margin-top:22px;width:100%;padding:14px;background:var(--accent-fill);color:#0c1400;border:none;border-radius:var(--radius-sm);font-size:1em;font-weight:700;cursor:pointer;transition:background .2s,transform .2s var(--ease),box-shadow .2s;box-shadow:var(--shadow-sm)}
.form-wrap button:hover{background:var(--accent2);transform:translateY(-1px);box-shadow:var(--shadow-md)}
.form-success{background:rgba(111,174,0,.08);border:1px solid rgba(111,174,0,.3);border-radius:var(--radius-sm);padding:14px 18px;color:var(--accent);margin-bottom:20px;font-size:.92em}
.form-error{background:rgba(200,50,50,.08);border:1px solid rgba(200,50,50,.35);border-radius:var(--radius-sm);padding:14px 18px;color:#b3492e;margin-bottom:20px;font-size:.92em}

/* REQUESTS */
.req-id{color:var(--accent);font-weight:700;font-size:1.05em}

/* WA */
.wa-btn{display:inline-flex;align-items:center;gap:7px;background:#25D366;border:1px solid #25D366;color:#fff;text-decoration:none;padding:9px 15px;border-radius:var(--radius-sm);font-size:.83em;font-weight:600;transition:background .2s,transform .2s var(--ease)}
.wa-btn:hover{background:#1ebe5d;transform:translateY(-1px)}
.wa-float{position:fixed;bottom:28px;right:28px;z-index:9999;display:flex;align-items:center;gap:10px;background:#25D366;color:#fff;text-decoration:none;padding:14px 22px;border-radius:50px;font-weight:700;font-size:.94em;box-shadow:0 4px 20px rgba(37,211,102,.28);transition:background .2s,transform .2s var(--ease),box-shadow .2s}
.wa-float:hover{background:#1ebe5d;transform:translateY(-2px);box-shadow:0 8px 28px rgba(37,211,102,.36)}

/* FOOTER */
footer{background:var(--bg2);border-top:1px solid var(--border);padding:56px 40px 36px;margin-top:60px}
.footer-inner{max-width:1240px;margin:0 auto}
.footer-grid{display:grid;grid-template-columns:2fr 1fr 1fr;gap:44px;margin-bottom:40px}
.footer-logo{font-size:1.22em;font-weight:800;color:var(--accent);margin-bottom:10px;letter-spacing:-.01em}
.footer-brand p{color:var(--muted);font-size:.85em;max-width:270px;line-height:1.6}
.footer-col h5{color:var(--white);font-size:.85em;font-weight:700;letter-spacing:.04em;text-transform:uppercase;margin-bottom:15px}
.footer-col a{display:block;color:var(--muted);text-decoration:none;font-size:.85em;margin-bottom:10px;transition:color .15s}
.footer-col a:hover{color:var(--accent)}
.footer-bottom{border-top:1px solid var(--border);padding-top:24px;display:flex;justify-content:space-between;align-items:center}
.footer-bottom p{color:var(--muted);font-size:.82em}

/* 4-BIT QUANTIZATION */
.quant-compare{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}
.quant-col{border-radius:var(--radius-md);padding:18px;border:1px solid}
.quant-full{border-color:var(--border2);background:var(--bg2)}
.quant-4bit{border-color:rgba(111,174,0,.32);background:rgba(111,174,0,.05)}
.quant-label{font-size:.74em;font-weight:700;text-transform:uppercase;letter-spacing:.1em;margin-bottom:9px}
.quant-full .quant-label{color:var(--muted)}
.quant-4bit .quant-label{color:var(--accent)}
.quant-build{background:var(--bg3);border-radius:var(--radius-sm);padding:11px 15px;margin-top:11px;font-size:.83em;color:var(--muted);line-height:1.6}
.quant-build strong{color:var(--white)}
.quant-savings{display:inline-block;background:rgba(111,174,0,.12);border:1px solid rgba(111,174,0,.3);color:var(--accent);border-radius:6px;padding:2px 9px;font-size:.75em;font-weight:700;margin-left:8px}
.quant-note{background:linear-gradient(135deg,rgba(111,174,0,.07),rgba(111,174,0,.02));border:1px solid rgba(111,174,0,.25);border-left:4px solid var(--accent-fill);border-radius:var(--radius-md);padding:24px 28px;margin-top:26px}
.quant-note p{color:var(--muted);font-size:.91em;line-height:1.8}

/* TECH BADGES */
.tech-grid{display:flex;flex-wrap:wrap;gap:12px;margin-top:10px}
.tech-badge{background:var(--card);border:1px solid var(--border);border-radius:var(--radius-sm);padding:12px 21px;font-size:.87em;color:var(--text);font-weight:600;transition:border-color .2s,transform .2s var(--ease),color .2s}
.tech-badge:hover{border-color:var(--accent);transform:translateY(-2px);color:var(--accent)}

/* DISCLAIMER */
.price-disclaimer{background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius-sm);padding:11px 17px;font-size:.8em;color:var(--muted);margin-bottom:22px;line-height:1.6}

/* RESPONSIVE */
@media(max-width:1080px){
  .hdr-nav{display:none}
}
@media(max-width:880px){
  .hero{grid-template-columns:1fr;gap:28px;padding:36px 0 28px}
  .hero-visual{min-height:320px}
  .hero3d-metric{right:14px;top:14px;left:14px;padding:14px 16px;min-width:0}
  .hero3d-metric-num{font-size:1.5em}
  .hero3d-metric .m-grid{grid-template-columns:repeat(4,1fr);gap:8px}
  .hero3d-metric .m-val{font-size:.85em}
  .trust-strip{gap:16px 22px}
  .calc-card{grid-template-columns:1fr;gap:24px}
  .calc-row{grid-template-columns:repeat(2,1fr)}
  .featured-wrap{grid-template-columns:1fr;gap:28px}
  .fe-rack{display:none}
  .sizing-grid{grid-template-columns:1fr}
  .cluster-section,.contact-grid,.about-grid,.footer-grid{grid-template-columns:1fr}
  .feature-strip{grid-template-columns:repeat(2,1fr)}
  header{padding:12px 16px;gap:14px}
  .hdr-search{max-width:none}
  main{padding:0 14px 120px}
}
@media(max-width:600px){
  .quant-compare{grid-template-columns:1fr}
  .hdr-search{display:none}
  header .hdr-cta{display:none}
  .calc-row{grid-template-columns:1fr 1fr}
  .feature-strip{grid-template-columns:1fr}
  .wa-float .wa-label{display:none}
  .wa-float{padding:14px;border-radius:50%;bottom:20px;right:20px}
  .footer-bottom{flex-direction:column;gap:8px;text-align:center}
}
</style>
</head>
<body>
<div class="announce"><span class="pill">NEW</span>NVIDIA GB300 NVL72 is here.<a href="#gb300">Explore the enterprise AI factory &rarr;</a></div>
<header>
  <a class="brand-logo" href="/"><span class="mark">&#9889;</span>Maria's AI Hardware Store</a>
  <nav class="hdr-nav">
    <a href="#gpus">Hardware</a>
    <a href="#models">AI Models</a>
    <a href="#cluster">Clusters</a>
    <a href="#cluster-builder">Build Your Setup</a>
    <a href="#compare">Compare</a>
    <a href="#about">About</a>
  </nav>
  <div class="hdr-search">
    <span class="si">&#128269;</span>
    <input type="text" id="site-search" placeholder="Search hardware, models..." autocomplete="off">
  </div>
  <div class="hdr-actions">
    <a class="hdr-icon-btn" href="https://wa.me/17862134550?text=Hello%2C%20I%27m%20interested%20in%20learning%20more%20about%20your%20AI%20hardware%20solutions.%20Could%20someone%20from%20your%20team%20help%20me%20choose%20the%20right%20configuration%3F" target="_blank" rel="noopener" title="Chat on WhatsApp">
      <svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>
    </a>
    <a class="hdr-icon-btn" href="/requests" title="Your quote requests">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/></svg>
    </a>
    <a class="hdr-cta" href="/quote">Request Quote</a>
  </div>
</header>
<a class="wa-float" href="https://wa.me/17862134550?text=Hello%2C%20I%27m%20interested%20in%20learning%20more%20about%20your%20AI%20hardware%20solutions.%20Could%20someone%20from%20your%20team%20help%20me%20choose%20the%20right%20configuration%3F" target="_blank" rel="noopener">
  <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>
  <span class="wa-label">Live Support</span>
</a>
"""

HTML_FOOTER = """
<footer>
  <div class="footer-inner">
    <div class="footer-grid">
      <div class="footer-brand">
        <div class="footer-logo">&#9889; Maria's AI Hardware Store</div>
        <p style="color:var(--accent);font-size:.87em;margin-bottom:8px;font-weight:600">Enterprise AI Infrastructure &bull; GPU Clusters &bull; NVIDIA Solutions</p>
        <p style="color:var(--muted);font-size:.84em;margin-bottom:6px">&#128241; +1 (786) 213-4550 &bull; &#128231; mdwork3003@gmail.com</p>
        <p style="color:var(--muted);font-size:.81em;max-width:280px">Built with Python, Flask, PostgreSQL, and AWS EC2</p>
      </div>
      <div class="footer-col">
        <h5>Products</h5>
        <a href="#gpus">GPU Catalog</a>
        <a href="#compare">Comparison Table</a>
        <a href="#builds">Recommended Builds</a>
        <a href="/quote">Request a Solution Quote</a>
        <a href="/requests">View Requests</a>
      </div>
      <div class="footer-col">
        <h5>Contact Our Team</h5>
        <a href="https://wa.me/17862134550?text=Hi%20Maria!%20I%27m%20interested%20in%20your%20AI%20hardware%20solutions." target="_blank">&#128241; WhatsApp +1 (786) 213-4550</a>
        <a href="mailto:mdwork3003@gmail.com">&#128231; mdwork3003@gmail.com</a>
        <a href="#about">About Maria</a>
      </div>
    </div>
    <div class="footer-bottom">
      <p>&#169; 2026 Maria Deiko &middot; Maria's AI Hardware Store</p>
      <p>Enterprise AI Infrastructure &middot; GPU Clusters &middot; NVIDIA Solutions</p>
    </div>
    <p style="color:var(--muted);font-size:.76em;text-align:center;margin-top:16px;padding-top:16px;border-top:1px solid var(--border);line-height:1.6">
      &#9432; Hardware prices are approximate and may vary by vendor, availability, configuration, and market demand. Always confirm final pricing before purchase.
    </p>
  </div>
</footer>
<script>
(function(){
  var obs = new IntersectionObserver(function(entries){
    entries.forEach(function(e){
      if(e.isIntersecting){ e.target.classList.add('visible'); }
    });
  }, {threshold: 0.08});
  document.querySelectorAll('.fade-in').forEach(function(el){ obs.observe(el); });
})();
</script>

<script>
// ---- client-side search: filters the GPU catalog, AI model cards, and
// featured-hardware carousel by name/description. Front-end only — there is
// no search backend/route in this app, this just shows/hides existing cards.
(function(){
  var input = document.getElementById('site-search');
  if(!input) return;
  var targets = document.querySelectorAll('.gpu-card[data-search], .model-card[data-search], .pcard[data-search]');
  input.addEventListener('input', function(){
    var q = input.value.trim().toLowerCase();
    targets.forEach(function(el){
      var match = !q || (el.getAttribute('data-search') || '').indexOf(q) !== -1;
      el.style.display = match ? '' : 'none';
    });
    if(q){
      var anyGpuMatch = Array.prototype.some.call(
        document.querySelectorAll('.gpu-card[data-search]'),
        function(el){ return el.style.display !== 'none'; }
      );
      if(anyGpuMatch){
        var gpuSection = document.getElementById('gpus');
        if(gpuSection) gpuSection.scrollIntoView({behavior:'smooth', block:'start'});
      }
    }
  });
  document.addEventListener('keydown', function(e){
    if((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k'){
      e.preventDefault();
      input.focus();
    }
  });
})();
</script>

<script>
// ---- "Build Your AI Cluster" interactive calculator ----
// Reuses the exact same formula used throughout the site:
// parameters (B) x 1 GB x 1.2 overhead = minimum VRAM, sized against the
// flagship GPU (NVIDIA H200 SXM5). CALC_DATA is serialized server-side from
// the real MODELS/GPUS/BUILDS data structures — no numbers are invented.
(function(){
  var modelSel = document.getElementById('calc-model');
  if(!modelSel || typeof CALC_DATA === 'undefined') return;
  var precisionSel = document.getElementById('calc-precision');
  var companySel = document.getElementById('calc-company');

  var reqMemEl = document.getElementById('calc-req-mem');
  var gpuCountEl = document.getElementById('calc-gpu-count');
  var priceEl = document.getElementById('calc-price');
  var totalMemEl = document.getElementById('calc-total-mem');
  var powerEl = document.getElementById('calc-power');
  var deployEl = document.getElementById('calc-deploy');
  var ctaEl = document.getElementById('calc-cta');

  function deploymentLabel(count){
    if(count <= 2) return 'Single Server';
    if(count <= 8) return 'AI Cluster';
    return 'Enterprise Rack';
  }

  function recompute(){
    var model = CALC_DATA.models[parseInt(modelSel.value, 10)];
    var precisionBytes = parseInt(precisionSel.value, 10) === 4 ? 0.5 : 1;
    var raw = model.params * precisionBytes;
    var total = Math.round(raw * 1.2);
    var gpu = CALC_DATA.gpu;
    var count = Math.max(1, Math.ceil(total / gpu.mem));
    var totalMem = gpu.mem * count;
    var totalPrice = gpu.price * count;
    var totalPowerKW = (gpu.power * count / 1000);

    reqMemEl.textContent = total + ' GB';
    gpuCountEl.textContent = count;
    priceEl.textContent = '$' + totalPrice.toLocaleString('en-US');
    totalMemEl.textContent = totalMem.toLocaleString('en-US') + ' GB';
    powerEl.textContent = totalPowerKW.toFixed(1) + ' kW';
    deployEl.textContent = deploymentLabel(count);
    ctaEl.setAttribute('href', '/quote?build=' + companySel.value);
  }

  [modelSel, precisionSel, companySel].forEach(function(el){
    el.addEventListener('change', recompute);
  });
  recompute();
})();
</script>

<script>
// ---- Featured Hardware carousel (prev/next + dot indicators) ----
(function(){
  var track = document.getElementById('pcard-track');
  if(!track) return;
  var prevBtn = document.getElementById('pcard-prev');
  var nextBtn = document.getElementById('pcard-next');
  var dotsWrap = document.getElementById('pcard-dots');
  var cards = Array.prototype.slice.call(track.children);
  if(!cards.length) return;

  cards.forEach(function(_, i){
    var dot = document.createElement('span');
    if(i === 0) dot.className = 'active';
    dot.addEventListener('click', function(){ scrollToCard(i); });
    dotsWrap.appendChild(dot);
  });
  var dots = Array.prototype.slice.call(dotsWrap.children);

  function cardStep(){
    var rect = cards[0].getBoundingClientRect();
    var style = getComputedStyle(track);
    return rect.width + parseFloat(style.gap || 18);
  }
  function scrollToCard(i){
    track.scrollTo({ left: i * cardStep(), behavior: 'smooth' });
  }
  function updateActive(){
    var idx = Math.round(track.scrollLeft / cardStep());
    dots.forEach(function(d, i){ d.classList.toggle('active', i === idx); });
    prevBtn.disabled = track.scrollLeft <= 4;
    nextBtn.disabled = track.scrollLeft >= track.scrollWidth - track.clientWidth - 4;
  }
  prevBtn.addEventListener('click', function(){
    var idx = Math.max(0, Math.round(track.scrollLeft / cardStep()) - 1);
    scrollToCard(idx);
  });
  nextBtn.addEventListener('click', function(){
    var idx = Math.min(cards.length - 1, Math.round(track.scrollLeft / cardStep()) + 1);
    scrollToCard(idx);
  });
  track.addEventListener('scroll', function(){
    window.requestAnimationFrame(updateActive);
  });
  updateActive();
})();
</script>
</body>
</html>
"""

EMAIL_SVG = '<svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/></svg>'

@app.route('/')
def index():
    P = []
    P.append(HTML_BASE)
    P.append('<main>')

    # ── HERO ──
    P.append(f'''
    <section class="hero">
      <div>
        <div class="hero-badge">Enterprise AI Infrastructure</div>
        <h1 class="hero-title">Power the Next<br><span>Generation of AI</span></h1>
        <p class="hero-sub">Enterprise GPU Solutions &bull; NVIDIA H200 &bull; GB300 &bull; AI Clusters</p>
        <p class="hero-msg">Find the right hardware in minutes with clear memory math, real prices, and human-friendly power estimates.</p>
        <div class="hero-btns">
          <a class="btn-primary" href="#cluster-builder">Build My AI Cluster &rarr;</a>
          <a class="btn-ghost" href="#gpus">Explore Hardware</a>
        </div>
        <div class="trust-strip">
          <div class="ti"><span class="ti-icon">&#10003;</span><div><div class="ti-name">Genuine NVIDIA</div><div class="ti-sub">Full manufacturer warranty</div></div></div>
          <div class="ti"><span class="ti-icon">&#10003;</span><div><div class="ti-name">Expert Support</div><div class="ti-sub">WhatsApp &amp; email direct</div></div></div>
          <div class="ti"><span class="ti-icon">&#10003;</span><div><div class="ti-name">Transparent Pricing</div><div class="ti-sub">No hidden markups</div></div></div>
        </div>
      </div>
      <div class="hero-visual" id="hero-visual">
        <img src="/static/img/hero-rack.jpg" alt="Enterprise NVIDIA GPU rack" width="1235" height="936">
        <div class="hero3d-metric fade-in" id="hero3d-metric">
          <div class="m-eyebrow"><span>&#9679;</span> GB300 NVL72 Spec</div>
          <div class="hero3d-metric-num" id="hero3d-metric-num">0<small>GB/s</small></div>
          <div class="hero3d-metric-lbl">NVLink Bandwidth</div>
          <div class="m-grid">
            <div><div class="m-val">{GB300['gpu_count']}</div><div class="m-lbl">GPUs</div></div>
            <div><div class="m-val">{GB300['per_gpu_memory']} GB</div><div class="m-lbl">HBM3e per GPU</div></div>
            <div><div class="m-val">{GB300['memory_gb']/1000:.1f} TB</div><div class="m-lbl">Total GPU Memory</div></div>
            <div><div class="m-val">{GB300['power_w']/1000:.0f} kW</div><div class="m-lbl">Typical Power</div></div>
          </div>
        </div>
      </div>
    </section>''')

    # ── HERO METRIC COUNT-UP (fires once when the hero scrolls into view) ──
    P.append('''
    <script>
    (function(){
      var mount = document.getElementById('hero-visual');
      if(!mount) return;
      var numEl = document.getElementById('hero3d-metric-num');
      var TARGET = 900;
      var counted = false;
      function countUp(){
        if(counted) return; counted = true;
        var start = null, dur = 1400;
        function step(ts){
          if(!start) start = ts;
          var p = Math.min(1, (ts - start) / dur);
          var eased = 1 - Math.pow(1 - p, 3);
          numEl.textContent = Math.round(eased * TARGET);
          if(p < 1) requestAnimationFrame(step); else numEl.textContent = TARGET;
        }
        requestAnimationFrame(step);
      }
      var metricObs = new IntersectionObserver(function(entries){
        entries.forEach(function(e){
          if(e.isIntersecting){ countUp(); metricObs.disconnect(); }
        });
      }, {threshold: 0.4});
      metricObs.observe(mount);
    })();
    </script>''')

    # ── HOW WE SIZE YOUR AI SYSTEM ──
    P.append('''
    <section class="fade-in">
      <div class="sec-label">How It Works</div>
      <div class="sec-title">How We Size Your AI System</div>
      <div class="sizing-grid">
        <div class="sizing-step">
          <div class="sizing-num">1</div>
          <div><strong>Choose the model</strong><p>Pick from Llama, DeepSeek, and other leading open-source models.</p></div>
        </div>
        <div class="sizing-step">
          <div class="sizing-num">2</div>
          <div><strong>Calculate memory</strong><p>Parameters &times; 1 GB + 20% overhead</p></div>
        </div>
        <div class="sizing-step">
          <div class="sizing-num">3</div>
          <div><strong>Match real hardware</strong><p>We map the requirement to real NVIDIA GPUs.</p></div>
        </div>
      </div>
      <div class="sizing-example">
        <strong style="color:var(--white)">Example:</strong> Llama 3.1 405B &rarr; <span class="mem-result">486 GB minimum</span> &rarr; 7&times; H100 80GB <em style="color:var(--muted)">or</em> 4&times; H200 141GB
      </div>
    </section>''')

    # ── BUILD YOUR AI CLUSTER (interactive calculator) ──
    calc_gpu = GPUS[0]  # NVIDIA H200 SXM5 — the flagship GPU we size against
    default_params = MODELS[0]['params_b']
    default_raw = min_vram_gb(default_params)
    default_count = -(-default_raw // calc_gpu['memory_gb'])
    calc_data = {
        'models': [{'name': m['name'], 'params': m['params_b']} for m in MODELS],
        'gpu': {'name': calc_gpu['name'], 'mem': calc_gpu['memory_gb'], 'price': calc_gpu['price'], 'power': calc_gpu['power_w']},
        'builds': {bkey: b['path'] for bkey, b in BUILDS.items()},
    }
    P.append(f'''
    <section id="cluster-builder" class="fade-in">
      <div class="calc-card">
        <div>
          <div class="calc-intro"><h3>Build Your AI Cluster</h3><span class="calc-tag">Interactive Calculator</span></div>
          <p class="calc-desc">Select your model and preferences. We'll calculate the right hardware for your needs using the same formula shown throughout this site: parameters &times; 1 GB + 20% overhead.</p>
          <div class="calc-field">
            <label>Model Size (Parameters)</label>
            <select id="calc-model">{''.join(f'<option value="{i}"{" selected" if i==0 else ""}>{m["name"]} ({m["params_b"]}B)</option>' for i, m in enumerate(MODELS))}</select>
          </div>
          <div class="calc-field">
            <label>Precision</label>
            <select id="calc-precision">
              <option value="16" selected>FP16 (16-bit)</option>
              <option value="4">4-bit Quantized (INT4)</option>
            </select>
          </div>
          <div class="calc-field">
            <label>Company Size</label>
            <select id="calc-company">
              <option value="small_startup">Small Startup</option>
              <option value="mid_company" selected>Mid-size Company</option>
              <option value="enterprise">Enterprise</option>
            </select>
          </div>
        </div>
        <div class="calc-results">
          <div class="calc-row">
            <div class="calc-stat"><div class="cs-lbl">Required GPU Memory</div><div class="cs-val" id="calc-req-mem">{default_raw} GB</div><div class="cs-sub">Minimum</div></div>
            <div class="calc-stat"><div class="cs-lbl">Recommended GPU</div><div class="cs-val" id="calc-gpu-name">{calc_gpu['name'].replace('NVIDIA ', '')}</div><div class="cs-sub">{calc_gpu['memory_gb']} GB HBM3e</div></div>
            <div class="calc-stat"><div class="cs-lbl">GPUs Needed</div><div class="cs-val" id="calc-gpu-count">{default_count}</div><div class="cs-sub">GPUs</div></div>
            <div class="calc-stat"><div class="cs-lbl">Est. System Price</div><div class="cs-val" id="calc-price">${calc_gpu['price']*default_count:,}</div><div class="cs-sub">USD</div></div>
          </div>
          <div class="calc-row">
            <div class="calc-stat"><div class="cs-lbl">Total GPU Memory</div><div class="cs-val" id="calc-total-mem">{calc_gpu['memory_gb']*default_count:,} GB</div></div>
            <div class="calc-stat"><div class="cs-lbl">Est. Power Usage</div><div class="cs-val" id="calc-power">{calc_gpu['power_w']*default_count/1000:.1f} kW</div></div>
            <div class="calc-stat"><div class="cs-lbl">Deployment Type</div><div class="cs-val" id="calc-deploy">AI Cluster</div></div>
          </div>
          <div class="calc-cta-row">
            <a class="calc-cta" id="calc-cta" href="/quote?build=mid_company">Request This Configuration &rarr;</a>
            <span class="calc-note">Pre-fills the quote form</span>
          </div>
        </div>
      </div>
    </section>
    <script>var CALC_DATA = {json.dumps(calc_data)};</script>''')

    # ── FEATURED NVIDIA HARDWARE (carousel) ──
    pcards = []
    for gpu in GPUS:
        badge = ''
        if gpu['badge_cls'] in ('bdg-popular', 'bdg-frontier'):
            badge = f'<span class="pcard-badge">{gpu["badge_label"]}</span>'
        pcards.append(f'''
        <div class="pcard" data-search="{gpu['name'].lower()} {gpu['description'].lower()}">
          {badge}
          <div class="pcard-img">{SVG[gpu['type']]}</div>
          <h4>{gpu['name']}</h4>
          <div class="pcard-spec">{gpu['memory_gb']} GB &bull; {gpu['power_w']} W</div>
          <div class="pcard-price">${gpu['price']:,}</div>
        </div>''')
    P.append(f'''
    <section id="featured-hardware" class="fade-in">
      <div class="carousel-head">
        <div><div class="sec-label">Shop Hardware</div><div class="sec-title" style="margin-bottom:0">Featured NVIDIA Hardware</div></div>
        <a class="view-all" href="#gpus">View all hardware &rarr;</a>
      </div>
      <div class="carousel-wrap">
        <div class="carousel-track" id="pcard-track">{''.join(pcards)}</div>
      </div>
      <div class="carousel-controls">
        <button class="carousel-nav" id="pcard-prev" aria-label="Previous">&#8592;</button>
        <div class="carousel-dots" id="pcard-dots"></div>
        <button class="carousel-nav" id="pcard-next" aria-label="Next">&#8594;</button>
      </div>
    </section>''')

    # ── FEATURED GB300 ──
    specs_html = ''.join(
        f'<div class="fe-spec"><div class="fe-spec-val">{v}</div><div class="fe-spec-lbl">{l}</div></div>'
        for v, l in GB300['specs']
    )
    cases_html = ''.join(f'<li>{c}</li>' for c in GB300['use_cases'])
    P.append(f'''
    <section id="gb300" class="fade-in">
      <div class="sec-label">Featured Enterprise Solution</div>
      <div class="featured-wrap">
        <div class="fe-rack">{GB300_RACK_SVG}</div>
        <div>
          <div class="fe-badge">&#128640; Next-Generation AI Factory</div>
          <div class="fe-title">NVIDIA GB300 NVL72</div>
          <div class="fe-sub">72 B300 GPUs · 13,824 GB Total VRAM · Single Rack</div>
          <p class="fe-desc">{GB300["description"]}</p>
          <div class="fe-specs">{specs_html}</div>
          <p style="color:var(--muted);font-size:.84em;margin-bottom:8px">Best use cases:</p>
          <ul class="fe-cases">{cases_html}</ul>
          <div style="display:flex;gap:12px;flex-wrap:wrap;align-items:center">
            <a class="btn-primary" href="/quote">Request Enterprise Quote &rarr;</a>
            {wa_card_btn("Request Technical Consultation")}
          </div>
        </div>
      </div>
    </section>''')

    # ── GPU CATALOG ──
    P.append('<section id="gpus" class="fade-in">')
    P.append('<div class="sec-label">Hardware Catalog</div>')
    P.append('<div class="sec-title">NVIDIA GPU Lineup</div>')
    P.append('<p class="sec-sub">Every GPU listed with real specifications, real market prices, and honest assessments.</p>')
    P.append('<p class="price-disclaimer">&#9432; Hardware prices are approximate and may vary by vendor, availability, configuration, and market demand. Always confirm final pricing before purchase.</p>')
    P.append('<div class="cards">')
    for gpu in GPUS:
        name = gpu['name']
        price = gpu['price']
        mem = gpu['memory_gb']
        pw = gpu['power_w']
        desc = gpu['description']
        gtype = gpu['type']
        bi = gpu['badge_icon']
        bl = gpu['badge_label']
        bc = gpu['badge_cls']
        bf = gpu['best_for']
        cool = gpu['cooling']
        dep = gpu['deployment']
        wrk = gpu['workload']
        war = gpu['warranty']
        avail = gpu['availability']
        elec = gpu['elec_year']
        homes = pw / HOME_WATTS
        icon_svg = SVG[gtype]
        wa_b = wa_card_btn()
        P.append(f'''
        <div class="gpu-card" data-search="{name.lower()} {desc.lower()} {bl.lower()}">
          <div class="gpu-icon">{icon_svg}</div>
          <span class="bdg {bc}">{bi} {bl}</span>
          <h3 style="color:var(--white);margin-bottom:4px">{name}</h3>
          <p style="color:var(--muted);font-size:.85em;margin-bottom:10px">{desc}</p>
          <div class="gpu-price">${price:,}</div>
          <div class="spec-row"><span class="spec-icon">&#128190;</span><span>Memory: <strong>{mem} GB</strong></span></div>
          <div class="spec-row"><span class="spec-icon">&#9889;</span><span>Power: <strong>{pw} W</strong></span></div>
          <div class="spec-row"><span class="spec-icon">&#127968;</span><span>Power = <strong>{homes:.1f} homes</strong> at 1,200 W each</span></div>
          <div class="spec-row"><span class="spec-icon">&#128267;</span><span>Electricity: <strong>{elec}</strong> (at $0.12/kWh)</span></div>
          <hr class="spec-divider">
          <div class="spec-row"><span class="spec-icon">&#10052;</span><span>Cooling: <strong>{cool}</strong></span></div>
          <div class="spec-row"><span class="spec-icon">&#127970;</span><span>Deployment: <strong>{dep}</strong></span></div>
          <div class="spec-row"><span class="spec-icon">&#128736;</span><span>Workload: <strong>{wrk}</strong></span></div>
          <div class="spec-row"><span class="spec-icon">&#128274;</span><span>Warranty: <strong>{war}</strong></span></div>
          <div class="spec-row"><span class="spec-icon">&#9989;</span><span>Availability: <strong>{avail}</strong></span></div>
          <div class="card-actions">{wa_b}</div>
        </div>''')
    P.append('</div></section>')

    # ── HOW TO CHOOSE ──
    P.append('''
    <section id="how-to-choose" class="fade-in">
      <div class="sec-label">Buyer's Guide</div>
      <div class="sec-title">How to Choose Your GPU</div>
      <p class="sec-sub">Not sure what you need? Start with your VRAM requirement and work backwards.</p>
      <div class="htc-grid">
        <div class="htc-card">
          <div class="htc-vram">Need &lt; 50 GB VRAM</div>
          <div class="htc-arrow">&darr;</div>
          <div class="htc-gpu">NVIDIA RTX 6000 Ada</div>
          <div class="htc-price">$7,200</div>
          <div class="htc-note">Enough for 40B parameter models. Works in a standard workstation. Great starting point for small teams.</div>
          <a class="btn-primary" href="/quote?build=small_startup" style="font-size:.82em;padding:9px 18px;margin-top:8px;align-self:flex-start">Start Here &rarr;</a>
        </div>
        <div class="htc-card">
          <div class="htc-vram">Need ~100 GB VRAM</div>
          <div class="htc-arrow">&darr;</div>
          <div class="htc-gpu">NVIDIA H100 PCIe</div>
          <div class="htc-price">$26,000</div>
          <div class="htc-note">Run Falcon 180B and most open-source 70B–180B models. Standard PCIe — fits existing rack servers.</div>
          <a class="btn-primary" href="/quote?build=mid_company" style="font-size:.82em;padding:9px 18px;margin-top:8px;align-self:flex-start">Explore &rarr;</a>
        </div>
        <div class="htc-card">
          <div class="htc-vram">Need ~200 GB VRAM</div>
          <div class="htc-arrow">&darr;</div>
          <div class="htc-gpu">NVIDIA H200 SXM5</div>
          <div class="htc-price">$44,000</div>
          <div class="htc-note">Run Falcon 180B at full precision, or DeepSeek-V2 236B 4-bit quantized. Train dense models up to ~200B parameters. The current frontier GPU standard.</div>
          <a class="btn-primary" href="/quote?build=enterprise" style="font-size:.82em;padding:9px 18px;margin-top:8px;align-self:flex-start">Explore &rarr;</a>
        </div>
        <div class="htc-card">
          <div class="htc-vram">Need massive AI clusters</div>
          <div class="htc-arrow">&darr;</div>
          <div class="htc-gpu">NVIDIA GB300 NVL72</div>
          <div class="htc-price">~$3M+</div>
          <div class="htc-note">Train frontier models from scratch. 13,824 GB in one rack. The only option for true hyperscale AI factories.</div>
          <a class="btn-primary" href="/quote" style="font-size:.82em;padding:9px 18px;margin-top:8px;align-self:flex-start">Request Quote &rarr;</a>
        </div>
      </div>
    </section>''')

    # ── COMPARISON TABLE ──
    P.append('<section id="compare" class="fade-in">')
    P.append('<div class="sec-label">Side by Side</div>')
    P.append('<div class="sec-title">Full Product Comparison</div>')
    P.append('<p class="sec-sub">From starter workstations to hyperscale AI factories.</p>')
    P.append('<div class="tbl-wrap"><table><thead><tr><th>GPU / System</th><th>VRAM</th><th>Power</th><th>Price</th><th>Best For</th></tr></thead><tbody>')
    for row in COMPARISON:
        rn = row['name']
        rm = row['memory_gb']
        rp = row['power_w']
        rs = row['price_str']
        rb = row['best_for']
        rc = ' class="hyper"' if rn == 'GB300 NVL72 Rack' else ''
        P.append(f'<tr{rc}><td class="td-name">{rn}</td><td class="td-mem">{rm:,} GB</td><td>{rp:,} W</td><td>{rs}</td><td>{rb}</td></tr>')
    P.append('</tbody></table></div></section>')

    # ── MODEL MEMORY ──
    P.append('<section id="models" class="fade-in">')
    P.append('<div class="sec-label">Memory Math</div>')
    P.append('<div class="sec-title">AI Model Requirements</div>')
    P.append('<p class="sec-sub">Formula: <strong style="color:var(--accent)">Parameters (B) &times; 1 GB &times; 1.2 overhead</strong> = minimum VRAM to load the model.</p>')
    for model in MODELS:
        mname = model['name']
        mpb = model['params_b']
        mdesc = model['description']
        muse = model['use_case']
        raw = mpb
        total = min_vram_gb(raw)
        h100c = -(-total // 80)
        h200c = -(-total // 141)
        wa_b = wa_card_btn()
        P.append(f'''
        <div class="model-card" data-search="{mname.lower()} {mdesc.lower()} {muse.lower()}">
          <h3 style="color:var(--white)">{mname}</h3>
          <p style="color:var(--muted);font-size:.87em">{mdesc}</p>
          <p style="color:var(--muted);font-size:.81em;margin-top:4px">Use case: {muse}</p>
          <div class="mem-calc">
            <strong style="color:var(--accent)">Memory Calculation:</strong><br>
            {mpb} B params &times; 1 GB = {raw} GB raw weight<br>
            {raw} GB &times; 1.2 overhead = <span class="mem-result">{total} GB minimum VRAM</span><br><br>
            &#128313; {h100c}&times; H100 80 GB &nbsp;&nbsp;(${h100c * 32000:,} in GPUs)<br>
            &#128313; {h200c}&times; H200 141 GB &nbsp;(${h200c * 44000:,} in GPUs)
          </div>
          <div style="margin-top:12px">{wa_b}</div>
        </div>''')
    P.append('</section>')

    # ── 4-BIT QUANTIZATION ──
    P.append('''
    <section id="quantized" class="fade-in">
      <div class="sec-label">Budget-Friendly Option</div>
      <div class="sec-title">Lower-Cost Option: 4-Bit Quantized Large Models</div>
      <p class="sec-sub">Run very large models on significantly less hardware — a practical path for teams with budget constraints.</p>

      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px;margin-bottom:28px">
        <div class="explainer-box">
          <h4>&#128190; Why Full Precision Needs So Much VRAM</h4>
          <p>By default, large model weights are stored in 16-bit floating point. A 405B parameter model needs roughly 486 GB of VRAM just to load — requiring many high-end GPUs and significant cost.</p>
        </div>
        <div class="explainer-box">
          <h4>&#9889; What 4-Bit Quantization Does</h4>
          <p>Quantization compresses each model weight from 16 bits down to 4 bits. The same model now fits in roughly half the VRAM. Accuracy and speed may be slightly reduced, but the model remains highly capable for most tasks.</p>
        </div>
        <div class="explainer-box">
          <h4>&#128200; When to Use It</h4>
          <p>4-bit is ideal for testing, demos, internal tools, and inference workloads where absolute peak quality is not required. For production training or maximum accuracy, full precision is still recommended.</p>
        </div>
      </div>

      <div class="model-card">
        <h3 style="color:var(--white)">Meta Llama 3.1 405B — Full vs 4-Bit</h3>
        <p style="color:var(--muted);font-size:.87em">Meta&#39;s flagship open-source model. GPT-4 class performance.</p>
        <div class="quant-compare">
          <div class="quant-col quant-full">
            <div class="quant-label">Full Precision (16-bit)</div>
            <div class="mem-calc">
              <strong style="color:var(--muted)">Memory Calculation:</strong><br>
              405 B &times; 1 GB = 405 GB raw weight<br>
              405 GB &times; 1.2 overhead = <span style="color:var(--text);font-weight:700">486 GB minimum VRAM</span>
            </div>
            <div class="quant-build">
              <strong>Example build:</strong> 4&times; H200 141 GB = 564 GB<br>
              <span style="color:var(--muted)">GPU cost: ~$176,000</span>
            </div>
          </div>
          <div class="quant-col quant-4bit">
            <div class="quant-label">4-Bit Quantized <span class="quant-savings">&#9660; 50% VRAM</span></div>
            <div class="mem-calc">
              <strong style="color:var(--accent)">Memory Calculation:</strong><br>
              405 B &times; 0.5 GB = 202.5 GB compressed<br>
              202.5 GB &times; 1.2 overhead = <span class="mem-result">243 GB minimum VRAM</span>
            </div>
            <div class="quant-build">
              <strong>Lower-cost build:</strong> 4&times; H100 80 GB = 320 GB<br>
              <span style="color:var(--accent)">GPU cost: ~$128,000 &mdash; saves ~$48,000</span>
            </div>
          </div>
        </div>
      </div>

      <div class="model-card" style="margin-top:14px">
        <h3 style="color:var(--white)">DeepSeek-V2 236B — Full vs 4-Bit</h3>
        <p style="color:var(--muted);font-size:.87em">Mixture-of-Experts design. Efficient and highly capable for code and reasoning.</p>
        <div class="quant-compare">
          <div class="quant-col quant-full">
            <div class="quant-label">Full Precision (16-bit)</div>
            <div class="mem-calc">
              <strong style="color:var(--muted)">Memory Calculation:</strong><br>
              236 B &times; 1 GB = 236 GB raw weight<br>
              236 GB &times; 1.2 overhead = <span style="color:var(--text);font-weight:700">283 GB minimum VRAM</span>
            </div>
            <div class="quant-build">
              <strong>Example build:</strong> 4&times; H100 80 GB = 320 GB or 3&times; H200 141 GB = 423 GB<br>
              <span style="color:var(--muted)">GPU cost: ~$128,000&ndash;$132,000</span>
            </div>
          </div>
          <div class="quant-col quant-4bit">
            <div class="quant-label">4-Bit Quantized <span class="quant-savings">&#9660; 50% VRAM</span></div>
            <div class="mem-calc">
              <strong style="color:var(--accent)">Memory Calculation:</strong><br>
              236 B &times; 0.5 GB = 118 GB compressed<br>
              118 GB &times; 1.2 overhead = <span class="mem-result">142 GB minimum VRAM</span>
            </div>
            <div class="quant-build">
              <strong>Lower-cost build:</strong> 2&times; H100 80 GB = 160 GB<br>
              <span style="color:var(--accent)">GPU cost: ~$64,000 &mdash; saves ~$24,000&ndash;$64,000</span>
            </div>
          </div>
        </div>
      </div>

      <div class="quant-note">
        <p><strong style="color:var(--white)">&#128172; A note for customers considering quantization:</strong></p>
        <p style="margin-top:8px">For customers who want to experiment with very large models but cannot afford full precision hardware, 4-bit quantized models are the budget-friendly path. I would recommend full precision for maximum quality, but 4-bit is a smart lower-cost option for testing and many inference workloads. It lets smaller teams access frontier-class models without frontier-class hardware budgets.</p>
      </div>
    </section>''')

    # ── CLUSTER VIZ ──
    P.append(f'''
    <section id="cluster" class="fade-in">
      <div class="sec-label">How It Works</div>
      <div class="sec-title">AI Clusters Explained</div>
      <div class="cluster-section">
        <div class="cluster-diagram">{CLUSTER_SVG}</div>
        <div>
          <p style="color:var(--muted);margin-bottom:16px">A <strong style="color:var(--accent)">cluster</strong> is multiple server machines connected over a high-speed network so they can share work — acting like one much bigger AI computer.</p>
          <div class="explainer-box">
            <h4>&#127970; Real Datacenter Cluster</h4>
            <p>Multiple dedicated servers, each holding 8 H100s, connected via InfiniBand or NVLink switches. GPUs across machines can share memory and compute. This is how companies like Meta train Llama 405B.</p>
          </div>
          <div class="explainer-box">
            <h4>&#128421; Several Desktop GPUs</h4>
            <p>Multiple RTX 4090s in one machine share a PCIe bus but cannot natively share VRAM across cards. They can run inference in parallel but cannot split one large model across machines without special software.</p>
          </div>
          <div class="explainer-box">
            <h4>&#9889; Why It Matters</h4>
            <p>A 4-machine cluster of 8&times; H100 each gives you 640 GB of unified, addressable VRAM — enough to run or train Llama 405B. 32 desktop GPUs cannot achieve this without complex engineering workarounds.</p>
          </div>
        </div>
      </div>
    </section>''')

    # ── RECOMMENDED BUILDS ──
    P.append('<section id="builds" class="fade-in">')
    P.append('<div class="sec-label">Recommended Configurations</div>')
    P.append('<div class="sec-title">Builds by Team Size</div>')
    P.append('<p class="sec-sub">Pre-calculated setups for real-world AI workloads with full power and cost breakdowns.</p>')
    pill_map = {"Small Startup": "pill-startup", "Mid-size Company": "pill-mid", "Enterprise": "pill-ent"}
    for bkey, build in BUILDS.items():
        gpu = build['gpu']
        count = build['count']
        gname = gpu['name']
        gmem = gpu['memory_gb']
        gpow = gpu['power_w']
        gprice = gpu['price']
        bname = build['name']
        bpath = build['path']
        bdesc = build['description']
        total_mem = gmem * count
        total_pow = gpow * count
        total_price = gprice * count
        homes = total_pow / HOME_WATTS
        daily_kwh = (total_pow / 1000) * 24
        ev_per_day = daily_kwh / EV_KWH
        pill_cls = pill_map[bpath]
        use_html = ''.join(f'<li style="margin:4px 0 4px 16px">{u}</li>' for u in build['use_cases'])
        wa_b = wa_card_btn()
        P.append(f'''
        <div class="build-card">
          <span class="path-pill {pill_cls}">{bpath}</span>
          <h3 style="color:var(--white);margin-top:10px">{bname}</h3>
          <p style="color:var(--muted);margin-bottom:4px">{bdesc}</p>
          <div class="bld-stats">
            <div class="stat-box"><div class="stat-val">{count}&times;</div><div class="stat-lbl">{gname}</div></div>
            <div class="stat-box"><div class="stat-val">{total_mem:,} GB</div><div class="stat-lbl">Combined VRAM</div></div>
            <div class="stat-box"><div class="stat-val">{total_pow:,} W</div><div class="stat-lbl">Total Power</div></div>
            <div class="stat-box"><div class="stat-val">${total_price:,}</div><div class="stat-lbl">GPU Hardware Cost</div></div>
          </div>
          <div class="pwr-row">
            <div class="pwr-box"><span class="pwr-icon">&#127968;</span><div><strong>{homes:.1f} homes</strong><br><span style="color:var(--muted);font-size:.79em">at 1,200 W per home</span></div></div>
            <div class="pwr-box"><span class="pwr-icon">&#128267;</span><div><strong>{daily_kwh:.0f} kWh/day</strong><br><span style="color:var(--muted);font-size:.79em">{ev_per_day:.1f}&times; EV battery drained daily</span></div></div>
            <div class="pwr-box"><span class="pwr-icon">&#9889;</span><div><strong>Enterprise power</strong><br><span style="color:var(--muted);font-size:.79em">Requires dedicated circuit</span></div></div>
          </div>
          <div style="margin-top:14px">
            <p style="font-size:.83em;color:var(--muted);margin-bottom:6px">Good for:</p>
            <ul style="color:var(--muted);font-size:.86em;line-height:1.8">{use_html}</ul>
          </div>
          <div style="margin-top:18px;display:flex;gap:12px;flex-wrap:wrap;align-items:center">
            <a class="btn-primary" href="/quote?build={bkey}" style="font-size:.87em;padding:10px 20px">Request a Quote &rarr;</a>
            {wa_b}
          </div>
        </div>''')
    P.append('</section>')

    # ── TRUST SECTION ──
    P.append('''
    <section id="trust" class="fade-in">
      <div class="sec-label">Why Trust Us</div>
      <div class="sec-title">Why Customers Trust Maria's AI Hardware Store</div>
      <p class="sec-sub" style="margin-bottom:22px">No upselling. No vague specs. Just clear answers to hard hardware questions.</p>
      <div class="trust-grid">
        <div class="trust-item">
          <div class="trust-check">&#10003;</div>
          <div><h4>Real NVIDIA Hardware</h4><p>Every product listed is genuine, current-generation NVIDIA hardware — no grey market, no knockoffs.</p></div>
        </div>
        <div class="trust-item">
          <div class="trust-check">&#10003;</div>
          <div><h4>Verified Specifications</h4><p>All VRAM, power draw, and performance specs sourced directly from NVIDIA product datasheets.</p></div>
        </div>
        <div class="trust-item">
          <div class="trust-check">&#10003;</div>
          <div><h4>Transparent Memory Calculations</h4><p>We show you exactly how much VRAM each model needs and why — no black-box recommendations.</p></div>
        </div>
        <div class="trust-item">
          <div class="trust-check">&#10003;</div>
          <div><h4>PostgreSQL-Backed Quote System</h4><p>Every quote request is saved securely in a PostgreSQL database. Nothing gets lost.</p></div>
        </div>
        <div class="trust-item">
          <div class="trust-check">&#10003;</div>
          <div><h4>Personal WhatsApp Consultation</h4><p>Text Maria directly. Get a real, personalized answer in hours — not a form email from a sales team.</p></div>
        </div>
        <div class="trust-item">
          <div class="trust-check">&#10003;</div>
          <div><h4>Honest Enterprise Recommendations</h4><p>We recommend what you actually need, not the most expensive configuration in the catalog.</p></div>
        </div>
      </div>
    </section>''')

    # ── ABOUT MARIA ──
    P.append(f'''
    <section id="about" class="fade-in">
      <div class="sec-label">About the Founder</div>
      <div class="about-grid">
        <div class="about-avatar">&#128105;</div>
        <div class="about-content">
          <h2>About Maria Deiko</h2>
          <p>Hi, I'm Maria Deiko.</p>
          <p>I'm studying Cloud Engineering and DevOps and building practical AI infrastructure solutions.</p>
          <p>I created Maria's AI Hardware Store to help startups, engineers, and businesses understand NVIDIA hardware without confusing specification sheets. The goal is simple: explain GPU memory, power usage, pricing, and model requirements in clear human language.</p>
          <div class="about-contacts">
            <div class="about-contact-item">
              <div class="aci-lbl">&#128241; WhatsApp</div>
              <div class="aci-val">+1 (786) 213-4550</div>
            </div>
            <div class="about-contact-item">
              <div class="aci-lbl">&#128231; Email</div>
              <div class="aci-val"><a href="mailto:mdwork3003@gmail.com" style="color:var(--accent);text-decoration:none">mdwork3003@gmail.com</a></div>
            </div>
          </div>
          <div class="about-btns">
            <a class="btn-wa" href="{WA_FLOAT_LINK}" target="_blank" rel="noopener">{WA_SVG_LG} WhatsApp Maria</a>
            <a class="btn-email" href="mailto:mdwork3003@gmail.com">{EMAIL_SVG} mdwork3003@gmail.com</a>
          </div>
        </div>
      </div>
    </section>''')

    # ── BUILT WITH ──
    P.append('''
    <section id="built-with" class="fade-in">
      <div class="sec-label">Technology Stack</div>
      <div class="sec-title">Built With</div>
      <div class="tech-grid">
        <div class="tech-badge">&#128013; Python</div>
        <div class="tech-badge">&#127760; Flask</div>
        <div class="tech-badge">&#128024; PostgreSQL</div>
        <div class="tech-badge">&#9729; Amazon EC2</div>
        <div class="tech-badge">&#128039; Linux</div>
        <div class="tech-badge">&#9881; systemd</div>
        <div class="tech-badge">&#128196; HTML</div>
        <div class="tech-badge">&#127912; CSS</div>
        <div class="tech-badge">&#10024; JavaScript</div>
      </div>
    </section>''')

    # ── WHY CHOOSE (dark bottom feature strip) ──
    P.append('''
    <section id="why" class="fade-in">
      <div class="feature-strip">
        <div class="fs-item"><span class="fs-icon">&#129504;</span><div><h4>Honest Recommendations</h4><p>What you actually need — not the most expensive option in the catalog.</p></div></div>
        <div class="fs-item"><span class="fs-icon">&#128200;</span><div><h4>Real Hardware Numbers</h4><p>Real VRAM, power draw, and prices. No marketing ranges or "up to" specs.</p></div></div>
        <div class="fs-item"><span class="fs-icon">&#129518;</span><div><h4>Clear Memory Math</h4><p>The exact VRAM formula for every major open-source model.</p></div></div>
        <div class="fs-item"><span class="fs-icon">&#128203;</span><div><h4>Enterprise Quote Support</h4><p>Custom quotes for multi-node clusters and full rack deployments.</p></div></div>
        <div class="fs-item"><span class="fs-icon">&#128241;</span><div><h4>WhatsApp Consultation</h4><p>Text Maria directly. A real answer in minutes.</p></div></div>
      </div>
    </section>''')

    # ── CONTACT ──
    P.append(f'''
    <section id="contact" class="fade-in">
      <div class="sec-label">Get in Touch</div>
      <div class="sec-title">Contact Our AI Infrastructure Team</div>
      <div class="contact-grid">
        <div class="contact-card">
          <p class="contact-intro">Our specialists can help you choose the right NVIDIA hardware, estimate infrastructure costs, and recommend the best solution for your AI workloads.</p>
          <div class="contact-line">
            <span class="ci-icon">&#128241;</span>
            <div><div class="ci-lbl">WhatsApp</div><div class="ci-val">+1 (786) 213-4550</div></div>
          </div>
          <div class="contact-line">
            <span class="ci-icon">&#128231;</span>
            <div><div class="ci-lbl">Email</div><div class="ci-val"><a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a></div></div>
          </div>
          <div class="contact-btns">
            <a class="btn-wa" href="{WA_FLOAT_LINK}" target="_blank" rel="noopener">{WA_SVG_SM} Talk to a Specialist</a>
            <a class="btn-email" href="mailto:{CONTACT_EMAIL}">{EMAIL_SVG} Email Our Team</a>
          </div>
        </div>
        <div class="contact-card">
          <p style="color:var(--muted);font-size:.9em;margin-bottom:18px">Or submit a quote request and Maria will follow up with a custom recommendation tailored to your workload and budget.</p>
          <a class="btn-primary" href="/quote" style="display:inline-flex;gap:8px;align-items:center">Request a Custom Quote &rarr;</a>
          <p style="color:var(--muted);font-size:.81em;margin-top:18px;line-height:1.7">Response time: &lt;2 hours on WhatsApp &bull; &lt;24 hours on email during business hours (EST).</p>
        </div>
      </div>
    </section>''')

    P.append('</main>')
    P.append(HTML_FOOTER)
    return ''.join(P)


@app.route('/quote', methods=['GET', 'POST'])
def quote():
    preselect = request.args.get('build', '')
    success = request.args.get('success') == '1'
    error = None
    form_name = ''
    form_contact = ''

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        contact = request.form.get('contact', '').strip()
        selected_build = request.form.get('selected_build', '').strip()
        form_name, form_contact = name, contact

        if not (name and contact and selected_build):
            error = "Please fill in your name, contact info, and a configuration."
        elif selected_build not in VALID_BUILD_NAMES:
            # selected_build is client-supplied — never trust it blindly before insert
            error = "Please choose a valid configuration from the list."
        else:
            try:
                conn = get_db()
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO quote_requests (name, contact, selected_build) VALUES (%s, %s, %s)",
                    (name, contact, selected_build)
                )
                conn.commit()
                cur.close()
                conn.close()
                # Post/Redirect/Get: prevents a page refresh from re-submitting the form
                return redirect(url_for('quote', success=1))
            except Exception:
                error = "Something went wrong saving your request. Please try again, or contact us directly on WhatsApp."

    P = [HTML_BASE, '<main style="padding-top:36px">']
    P.append('<div class="sec-label">Get Started</div>')
    P.append('<h2 style="color:var(--white);font-size:1.85em;margin-bottom:22px">Request a Quote</h2>')
    if success:
        P.append('<div class="form-success">&#10003; Your quote request has been saved to our database. Maria will be in touch shortly.</div>')
    if error:
        P.append(f'<div class="form-error">&#9888; {error}</div>')
    P.append('<form method="POST"><div class="form-wrap">')
    P.append(f'<label>Your Name</label><input type="text" name="name" required placeholder="Jane Smith" value="{html.escape(form_name)}">')
    P.append(f'<label>Email or WhatsApp Number</label><input type="text" name="contact" required placeholder="jane@company.com or +1 555 0100" value="{html.escape(form_contact)}">')
    P.append('<label>Select a Configuration</label><select name="selected_build" required>')
    P.append('<option value="">-- Choose a configuration --</option>')
    for bkey, build in BUILDS.items():
        sel = 'selected' if bkey == preselect else ''
        gpu = build['gpu']
        count = build['count']
        bname = build['name']
        total = gpu['price'] * count
        gname = gpu['name']
        P.append(f'<option value="{bname}" {sel}>{bname} — ${total:,} ({count}x {gname})</option>')
    P.append(f'<option value="{GB300_QUOTE_OPTION}">{GB300_QUOTE_OPTION} Quote</option>')
    P.append('</select>')
    P.append('<button type="submit">Submit Quote Request</button>')
    P.append('</div></form>')
    P.append('</main>')
    P.append(HTML_FOOTER)
    return ''.join(P)


@app.route('/requests')
def requests_list():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT * FROM quote_requests ORDER BY created_at DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    P = [HTML_BASE, '<main style="padding-top:36px">']
    total = len(rows)
    P.append(f'<div class="sec-label">Database</div>')
    P.append(f'<h2 style="color:var(--white);font-size:1.85em;margin-bottom:22px">Quote Requests ({total} total)</h2>')
    if not rows:
        P.append('<p style="color:var(--muted)">No requests yet. <a href="/quote" style="color:var(--accent)">Submit the first one!</a></p>')
    else:
        P.append('<div class="tbl-wrap"><table><thead><tr><th>#</th><th>Name</th><th>Contact</th><th>Selected Build</th><th>Submitted</th></tr></thead><tbody>')
        for row in rows:
            rid = row['id']
            rname = html.escape(row['name'])
            rcontact = html.escape(row['contact'])
            rbuild = html.escape(row['selected_build'])
            rtime = row['created_at'].strftime('%Y-%m-%d %H:%M UTC')
            P.append(f'<tr><td class="req-id">#{rid}</td><td>{rname}</td><td>{rcontact}</td><td>{rbuild}</td><td style="color:var(--muted);font-size:.84em">{rtime}</td></tr>')
        P.append('</tbody></table></div>')
    P.append('</main>')
    P.append(HTML_FOOTER)
    return ''.join(P)


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8080, debug=False)
