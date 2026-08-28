# AI Lead Intelligence & Sales Prospecting Platform

## 1. Project Overview

### Project Name
**AI Lead Intelligence & Sales Prospecting Platform**

### Purpose

Build an internal sales-intelligence platform for a software development startup that automatically discovers local businesses, analyzes customer reviews for software-related pain points, identifies potential software opportunities, ranks leads, and generates sales-ready information for cold calling.

The system should transform:

> **Location + Business Category + Rating + Lead Count**

into:

> **Qualified business leads + customer pain points + software opportunities + lead score + personalized cold-call pitch + CSV export**

---

# 2. Core Problem

A sales team normally has to manually:

1. Search Google Maps.
2. Find businesses in a target category.
3. Check ratings and reviews.
4. Read negative reviews.
5. Determine whether complaints indicate software problems.
6. Visit the business website.
7. Find contact details.
8. Determine what technology the business already uses.
9. Decide whether the business is a good prospect.
10. Write a personalized cold-call pitch.
11. Export the leads.

This is slow and difficult to scale.

The proposed platform automates this workflow.

---

# 3. Proposed Solution

The platform acts as an **AI-powered lead research assistant**.

Example input:

```text
Location: Chennai
Category: Clothing Stores
Rating Range: 3.0 - 4.0
Number of Leads: 5
Minimum Reviews: 20
```

The system:

```text
User Input
    ↓
Business Search
    ↓
Google Maps / Places + Apify
    ↓
Business Filtering
    ↓
Review Collection
    ↓
Negative / Problem Review Detection
    ↓
LLM Review Analysis
    ↓
Software Pain-Point Detection
    ↓
Technology / Website Analysis
    ↓
Software Opportunity Detection
    ↓
Lead Scoring
    ↓
Cold-Call Pitch Generation
    ↓
CSV Export + Dashboard
```

---

# 4. Example User Journey

## Input

```text
Location: Chennai
Category: Clothing Stores
Rating: Medium
Rating Range: 3.0 - 4.0
Minimum Reviews: 20
Number of Leads: 5
```

## Example Output

| Business | Rating | Reviews | Main Pain Point | Software Opportunity | Lead Score |
|---|---:|---:|---|---|---:|
| ABC Fashion | 3.6 | 218 | Long billing queues | POS System | 87 |
| XYZ Clothing | 3.8 | 97 | Stock mismatch | Inventory Management | 82 |
| PQR Fashion | 3.4 | 231 | Poor online ordering | E-commerce Platform | 79 |
| Fashion Hub | 3.9 | 65 | Poor customer communication | CRM / WhatsApp Automation | 76 |
| Style World | 3.5 | 142 | Website issues | Website Modernization | 73 |

---

# 5. Key Features

## 5.1 Business Search

Users can search businesses based on:

- Location
- Radius
- Category
- Rating range
- Number of businesses
- Minimum review count
- Business type

Example:

```text
Location: Chennai
Radius: 10 km
Category: Clothing Stores
Rating: 3.0 - 4.0
Leads: 5
Minimum Reviews: 20
```

---

## 5.2 Google Maps / Places Data Collection

Collect:

- Business name
- Category
- Rating
- Total review count
- Address
- Phone
- Website
- Google Maps URL
- Latitude
- Longitude
- Reviews
- Review ratings
- Review text
- Review dates
- Other available business metadata

### Recommended approach

Use **Apify** as the initial scraping provider.

Optionally use **Google Places API** for official place information.

The system should use an abstraction layer so the provider can be replaced later.

Example:

```python
class MapsProvider:
    def search_businesses(self, query, location):
        pass

    def get_business_details(self, place_id):
        pass

    def get_reviews(self, place_id):
        pass
```

Implementations:

```text
MapsProvider
    ├── ApifyProvider
    └── GooglePlacesProvider
```

---

# 6. Business Filtering

The scraper may return many businesses.

The backend should filter them before expensive processing.

Example:

```text
Search Results: 100 businesses
        ↓
Category Filter
        ↓
Rating Filter
        ↓
Minimum Review Filter
        ↓
Duplicate Removal
        ↓
Website / Contactability Filter
        ↓
Candidate Leads
```

Example condition:

```python
if 3.0 <= business.rating <= 4.0:
    keep_business()
```

Recommended filters:

```text
rating
review_count
category
location
distance
website_available
phone_available
duplicate_status
```

---

# 7. Review Analysis

This is the main AI component.

The system should not simply summarize reviews.

It should answer:

> "Does this review indicate a problem that our software company could potentially solve?"

Example review:

> "Good collection but billing took almost 30 minutes. Only one counter was open."

AI output:

```json
{
  "review_problem": "Long billing wait time",
  "problem_category": "POS / Billing",
  "severity": "high",
  "software_related": true,
  "business_impact": "Customers experience long waiting times during checkout",
  "software_solution": "Multi-counter POS and queue-aware billing system",
  "sales_opportunity": "High"
}
```

---

# 8. Review Categories

The LLM should classify complaints into categories such as:

```text
POS / Billing
Inventory Management
E-commerce
Website
Mobile App
CRM
Customer Communication
WhatsApp Automation
Booking / Appointment
Delivery Management
Payment Integration
Order Management
Loyalty / Rewards
Marketing Automation
Analytics / Reporting
Employee Management
Accounting Integration
Other
```

---

# 9. Negative Review Detection

Not every low-rated review is useful.

Examples:

### Useful

> "Website showed the product as available but it was actually out of stock."

Potential problem:

```text
Inventory synchronization
```

### Not useful

> "Food was bad."

This is probably not a software opportunity.

The system should distinguish:

```text
Customer dissatisfaction
        ≠
Software opportunity
```

---

# 10. Review Processing Pipeline

Do not send every review directly to the LLM.

Use a two-stage pipeline.

```text
All Reviews
    ↓
Deduplication
    ↓
Keyword / heuristic filtering
    ↓
Potentially relevant reviews
    ↓
LLM analysis
```

Potential keywords:

```text
slow
waiting
website
online
order
delivery
stock
inventory
billing
payment
customer service
call
WhatsApp
app
booking
refund
return
digital
software
system
website
login
account
payment
```

This reduces:

- LLM cost
- processing time
- unnecessary API calls

---

# 11. LLM Structured Output

The LLM should return structured JSON rather than unstructured text.

Example:

```json
{
  "software_related": true,
  "pain_point": "Long billing queue",
  "pain_category": "POS / Billing",
  "severity": "high",
  "customer_impact": "Customers experience long waiting times",
  "business_impact": "Potential customer dissatisfaction and lost sales",
  "recommended_solution": "Multi-counter POS system",
  "solution_type": "POS",
  "confidence": 0.91
}
```

Use JSON Schema / Structured Outputs so the backend receives predictable data.

---

# 12. Evidence-Based AI

This is an important project rule.

The AI must **not invent a business problem**.

Every detected problem should retain:

```text
Original review
Review rating
Review date
Review URL / source reference where available
AI interpretation
```

Example:

```text
Problem:
Long billing queues

Evidence:
"Had to wait almost 30 minutes to pay."

AI interpretation:
Possible POS/billing workflow issue.

Recommended solution:
Multi-counter POS system.

Confidence:
91%
```

This makes the sales intelligence trustworthy.

---

# 13. Website Analysis

After identifying a business, visit its website if available.

Collect:

```text
Website URL
Title
Description
Contact page
Email
Phone
Social links
E-commerce availability
Online ordering
Booking functionality
Payment functionality
Technology signals
```

---

# 14. Technology Detection

Determine what technology the business already uses.

Potential signals:

```text
WordPress
Shopify
WooCommerce
Magento
Custom website
WhatsApp
Online ordering
Booking system
Payment gateway
CRM
E-commerce
Inventory system
Mobile application
Analytics
```

Example:

```text
ABC Fashion

Website: Yes
E-commerce: Yes
Shopify: Yes
WhatsApp: Yes
Online Payment: Yes
Inventory Visibility: No
CRM: Unknown
```

Possible opportunity:

```text
Inventory + CRM Integration
```

---

# 15. Email Extraction

Google Maps data may not reliably contain email addresses.

Use the business website as the second source.

Pipeline:

```text
Business
   ↓
Website
   ↓
Contact/About page
   ↓
Email extraction
   ↓
Email validation
   ↓
Store email
```

Possible email patterns:

```text
info@
contact@
sales@
support@
hello@
business@
```

Do not fabricate an email address from the domain.

---

# 16. Lead Scoring

Create a lead score from 0 to 100.

Recommended model:

```text
Software Pain        40%
Business Potential   25%
Review Evidence      20%
Digital Presence     10%
Contactability        5%
```

Example:

```text
ABC Fashion

Software Pain:       87
Business Potential:  78
Review Evidence:     91
Digital Presence:    65
Contactability:      90

Final Lead Score:    83
Priority:            HOT
```

---

# 17. Lead Priority

Recommended classification:

```text
80 - 100 → HOT
60 - 79  → WARM
40 - 59  → COLD
0 - 39   → LOW
```

Example:

```text
Lead Score: 87
Priority: HOT
```

---

# 18. Sales Opportunity Detection

The AI should map pain points to potential software services.

Example mappings:

| Customer Complaint | Software Opportunity |
|---|---|
| Long billing queue | POS System |
| Stock mismatch | Inventory Management |
| Website unavailable | Website Development |
| Poor online ordering | E-commerce Platform |
| No response to customers | CRM / WhatsApp Automation |
| Appointment problems | Booking System |
| Payment failures | Payment Integration |
| Delivery complaints | Delivery Management |
| No customer follow-up | CRM |
| No loyalty program | Loyalty Platform |
| Manual reporting | Analytics Dashboard |
| Multiple spreadsheets | Business Management System |

---

# 19. Personalized Cold-Call Pitch

For each qualified lead, generate a short sales opening.

Example:

```text
Hi, I'm calling from XYZ Technologies.

We work with retail businesses to improve their billing
and inventory processes.

I noticed that customer feedback around billing wait times
can sometimes be challenging for retail stores.

I wanted to check if you're currently using a POS and
inventory management system, or if that's something
you're looking to improve?
```

The pitch should be based on actual evidence from reviews.

---

# 20. Recommended CSV Schema

The final CSV should contain:

```text
company_name
category
rating
total_reviews

phone
email
website

address
city
google_maps_url

latitude
longitude

review_rating
review_text
review_date
review_url

pain_point
pain_category
pain_severity

software_related
software_problem
customer_impact
business_impact

recommended_solution
solution_type

technology_signals

lead_score
lead_priority
confidence

sales_pitch
```

Example:

```csv
company_name,rating,phone,email,pain_point,software_problem,recommended_solution,lead_score,lead_priority,google_maps_url
ABC Fashion,3.6,+91XXXXXXXXXX,info@abc.com,Long billing queue,true,Multi-counter POS,87,HOT,...
XYZ Clothing,3.8,+91XXXXXXXXXX,contact@xyz.com,Stock mismatch,true,Inventory Management,82,HOT,...
PQR Fashion,3.4,+91XXXXXXXXXX,,Poor online ordering,true,E-commerce Platform,79,WARM,...
```

---

# 21. Dashboard

The UI should have two main screens.

## Search Screen

```text
┌──────────────────────────────────────────┐
│        AI LEAD INTELLIGENCE              │
├──────────────────────────────────────────┤
│                                          │
│ Location        [ Chennai            ]   │
│                                          │
│ Category        [ Clothing Stores    ]   │
│                                          │
│ Rating          [ 3.0 ] - [ 4.0 ]       │
│                                          │
│ Minimum Reviews [ 20 ]                   │
│                                          │
│ Number of Leads [ 5 ]                    │
│                                          │
│          [ Find Leads ]                  │
└──────────────────────────────────────────┘
```

## Results Screen

```text
HOT LEADS

ABC Fashion

Rating: 3.6
Reviews: 218
Location: Chennai

Lead Score: 87

Main Problem:
Long billing queues

Software Opportunity:
POS + Inventory

Customer Evidence:
"Had to wait almost 30 minutes..."

Recommended Solution:
Multi-counter POS + inventory system

[View Maps] [View Website] [Export]
```

---

# 22. Recommended Architecture

```text
                    ┌──────────────────┐
                    │     Frontend     │
                    │ Next.js / React  │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │     FastAPI      │
                    │     Backend      │
                    └────────┬─────────┘
                             │
            ┌────────────────┼────────────────┐
            ▼                ▼                ▼
     ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
     │    Apify     │ │ Google Places│ │   Website    │
     │    Scraper   │ │     API      │ │   Crawler    │
     └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
            │                │                │
            └────────────────┼────────────────┘
                             ▼
                    ┌──────────────────┐
                    │ Data Normalizer  │
                    │ Deduplication    │
                    └────────┬─────────┘
                             ▼
                    ┌──────────────────┐
                    │ Review Processor │
                    └────────┬─────────┘
                             ▼
                    ┌──────────────────┐
                    │   OpenAI LLM     │
                    │ Structured JSON  │
                    └────────┬─────────┘
                             ▼
                    ┌──────────────────┐
                    │ Lead Scoring     │
                    │ Opportunity      │
                    └────────┬─────────┘
                             ▼
                ┌────────────┴────────────┐
                ▼                         ▼
        ┌──────────────┐          ┌──────────────┐
        │ PostgreSQL   │          │ CSV Export   │
        └──────────────┘          └──────────────┘
```

---

# 23. Recommended Tech Stack

| Component | Technology |
|---|---|
| Frontend | Next.js |
| UI | Tailwind CSS |
| Backend | FastAPI |
| Programming Language | Python |
| Maps Data | Apify |
| Official Place Data | Google Places API |
| Website Crawler | httpx + BeautifulSoup / Playwright |
| LLM | OpenAI API |
| Structured Output | JSON Schema |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Background Jobs | Celery + Redis |
| CSV Processing | Pandas |
| Frontend Deployment | Vercel |
| Backend Deployment | Railway / Render |
| Database Hosting | Supabase |
| Scraper | Apify |

---

# 24. Fastest MVP Stack

Do not build the full production architecture immediately.

For V1 use:

```text
Python
+
Streamlit
+
Apify
+
OpenAI API
+
Pandas
+
SQLite/PostgreSQL
```

This is enough to validate the idea.

Once the sales team starts using it:

```text
Next.js
+
FastAPI
+
PostgreSQL
+
Redis
+
Celery
```

---

# 25. MVP Pipeline

The first version should implement:

```text
1. User enters location
2. User enters category
3. User selects rating range
4. User enters number of leads
5. Apify searches businesses
6. Backend filters businesses
7. Reviews are collected
8. Negative/problem reviews are identified
9. LLM analyzes reviews
10. Website is checked
11. Email/contact information is extracted
12. Software opportunity is generated
13. Lead score is calculated
14. Cold-call pitch is generated
15. CSV is created
```

---

# 26. Backend API Design

Recommended FastAPI endpoints:

```text
POST /api/search
POST /api/analyze/{lead_id}
GET  /api/leads
GET  /api/leads/{lead_id}
GET  /api/leads/{lead_id}/reviews
GET  /api/leads/{lead_id}/analysis
GET  /api/export/csv
POST /api/search/{job_id}/cancel
GET  /api/jobs/{job_id}
```

Example:

```http
POST /api/search
```

Request:

```json
{
  "location": "Chennai",
  "category": "Clothing Stores",
  "min_rating": 3.0,
  "max_rating": 4.0,
  "minimum_reviews": 20,
  "limit": 5
}
```

Response:

```json
{
  "job_id": "job_123",
  "status": "processing"
}
```

---

# 27. Background Processing

Scraping and LLM analysis may take time.

Do not keep the frontend request open.

Use:

```text
Frontend
   ↓
POST /api/search
   ↓
Create Job
   ↓
Queue Job
   ↓
Return job_id
```

Worker:

```text
Worker
 ↓
Apify
 ↓
Normalize
 ↓
Review processing
 ↓
LLM
 ↓
Scoring
 ↓
Database
```

Frontend:

```text
GET /api/jobs/{job_id}
```

until:

```text
status = completed
```

---

# 28. Database Schema

## businesses

```text
id
name
category
rating
review_count
phone
email
website
address
city
latitude
longitude
google_maps_url
created_at
updated_at
```

## reviews

```text
id
business_id
rating
text
review_date
review_url
source
created_at
```

## review_analysis

```text
id
review_id
software_related
pain_point
pain_category
severity
customer_impact
business_impact
recommended_solution
solution_type
confidence
created_at
```

## leads

```text
id
business_id
software_pain_score
business_potential_score
review_evidence_score
digital_presence_score
contactability_score
lead_score
priority
sales_pitch
created_at
```

## jobs

```text
id
location
category
min_rating
max_rating
minimum_reviews
requested_leads
status
progress
created_at
completed_at
```

---

# 29. Lead Scoring Formula

Example:

```python
lead_score = (
    software_pain_score * 0.40 +
    business_potential_score * 0.25 +
    review_evidence_score * 0.20 +
    digital_presence_score * 0.10 +
    contactability_score * 0.05
)
```

Example:

```text
Software Pain = 87
Business Potential = 78
Review Evidence = 91
Digital Presence = 65
Contactability = 90
```

Calculation:

```text
87 × 0.40 = 34.8
78 × 0.25 = 19.5
91 × 0.20 = 18.2
65 × 0.10 = 6.5
90 × 0.05 = 4.5

Total = 83.5
```

Final:

```text
Lead Score = 84
Priority = HOT
```

---

# 30. Suggested Project Folder Structure

```text
ai-lead-intelligence/
│
├── frontend/
│   ├── app/
│   ├── components/
│   ├── lib/
│   ├── hooks/
│   └── public/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   │
│   │   ├── api/
│   │   │   ├── search.py
│   │   │   ├── leads.py
│   │   │   ├── reviews.py
│   │   │   └── export.py
│   │   │
│   │   ├── models/
│   │   │   ├── business.py
│   │   │   ├── review.py
│   │   │   ├── lead.py
│   │   │   └── job.py
│   │   │
│   │   ├── schemas/
│   │   │   ├── search.py
│   │   │   ├── business.py
│   │   │   └── analysis.py
│   │   │
│   │   ├── services/
│   │   │   ├── apify_service.py
│   │   │   ├── maps_service.py
│   │   │   ├── review_service.py
│   │   │   ├── llm_service.py
│   │   │   ├── website_service.py
│   │   │   ├── email_service.py
│   │   │   ├── scoring_service.py
│   │   │   └── export_service.py
│   │   │
│   │   ├── workers/
│   │   │   └── search_worker.py
│   │   │
│   │   └── utils/
│   │       ├── text_filter.py
│   │       ├── deduplication.py
│   │       └── validators.py
│   │
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
│
├── prompts/
│   ├── review_analysis.txt
│   ├── opportunity_detection.txt
│   └── sales_pitch.txt
│
├── scripts/
│   ├── seed_data.py
│   └── test_apify.py
│
├── .env.example
├── docker-compose.yml
├── README.md
└── .gitignore
```

---

# 31. Environment Variables

Example:

```env
APIFY_API_TOKEN=your_apify_token
OPENAI_API_KEY=your_openai_key
GOOGLE_MAPS_API_KEY=your_google_maps_key

DATABASE_URL=postgresql://user:password@localhost:5432/leads

REDIS_URL=redis://localhost:6379
```

Never commit real API keys to Git.

---

# 32. AI Prompt Architecture

Use separate prompts for different tasks.

## Prompt 1: Review Classification

Input:

```text
Business:
ABC Fashion

Review:
"Had to wait almost 30 minutes to pay."
```

Output:

```json
{
  "software_related": true,
  "pain_point": "Long billing wait",
  "pain_category": "POS / Billing",
  "severity": "high",
  "business_impact": "Customer waiting time",
  "recommended_solution": "Multi-counter POS",
  "confidence": 0.92
}
```

---

## Prompt 2: Opportunity Detection

Input:

```text
Business category: Clothing Store

Problems:
1. Long billing queues
2. Stock mismatch
3. No online ordering
```

Output:

```json
{
  "primary_opportunity": "Retail POS + Inventory",
  "secondary_opportunities": [
    "E-commerce",
    "CRM"
  ],
  "sales_priority": "high"
}
```

---

## Prompt 3: Sales Pitch

Input:

```text
Business: ABC Fashion
Problem: Long billing queue
Solution: Multi-counter POS
Evidence: Several customers mention long waiting times
```

Output:

```text
Hi, I'm calling from XYZ Technologies...

We help retail stores improve billing and inventory
operations. I noticed customer feedback mentioning
long waiting times during billing, so I wanted to check
whether you're currently using a POS system that supports
multiple billing counters.
```

---

# 33. Important Design Principle

The platform should separate:

```text
FACT
↓
AI INTERPRETATION
↓
RECOMMENDATION
```

Example:

```text
FACT:
Customer waited 30 minutes.

INTERPRETATION:
Potential billing workflow issue.

RECOMMENDATION:
Evaluate multi-counter POS.

```

Do not represent the recommendation as a confirmed fact.

---

# 34. Performance Optimization

For fast execution:

### 1. Parallelize website requests

Instead of:

```text
Website A
wait
Website B
wait
Website C
wait
```

use asynchronous requests.

```text
Website A ─┐
Website B ─┼─→ parallel
Website C ─┘
```

### 2. Analyze only useful reviews

Use keyword/sentiment pre-filtering.

### 3. Batch LLM requests where practical

Analyze multiple reviews from one business in one structured LLM call when the output schema allows it.

### 4. Cache results

Do not repeatedly analyze the same review.

### 5. Deduplicate businesses

Normalize:

```text
ABC Fashion
ABC Fashion Store
ABC Fashions Chennai
```

before storing.

---

# 35. Reliability

Every pipeline stage should have failure handling.

Example:

```text
Apify fails
    ↓
Retry
    ↓
Still fails
    ↓
Mark job partial
```

Website unavailable:

```text
Website unavailable
    ↓
Continue with Maps data
```

Email unavailable:

```text
email = null
```

LLM failure:

```text
Retry
    ↓
Fallback status
```

Never stop the entire job because one business failed.

---

# 36. Compliance and Responsible Data Use

Before deploying commercially, review the applicable terms and policies for the data sources you use.

Important considerations:

- Follow Google Maps/Places API terms and attribution requirements.
- Respect Apify actor/data-source terms.
- Avoid collecting unnecessary personal information.
- Store only business-relevant contact information.
- Avoid fabricating contact details.
- Preserve source evidence for AI-generated conclusions.
- Provide clear provenance for review-derived insights.
- Implement rate limits and retries.
- Secure API keys.
- Protect stored lead data.

The system should focus primarily on **public business information and business-relevant customer feedback**, rather than sensitive personal data.

---

# 37. Security

Implement:

```text
API authentication
Rate limiting
Input validation
API key protection
Database access control
HTTPS
Encrypted secrets
Audit logs
```

Do not expose:

```text
APIFY_API_TOKEN
OPENAI_API_KEY
GOOGLE_MAPS_API_KEY
DATABASE_PASSWORD
```

to the frontend.

---

# 38. Development Phases

## Phase 1 — Proof of Concept

Build:

```text
Python
Apify
OpenAI
Pandas
CSV
```

Features:

- Search businesses
- Collect reviews
- Analyze reviews
- Generate software opportunity
- Export CSV

Goal:

> Prove that the AI can discover useful sales opportunities.

---

## Phase 2 — Internal MVP

Add:

```text
FastAPI
PostgreSQL
Streamlit / Next.js
```

Features:

- Search UI
- Lead dashboard
- Lead scoring
- Review evidence
- Website analysis
- Email extraction
- Cold-call pitch
- CSV export

---

## Phase 3 — Production Version

Add:

```text
Next.js
FastAPI
PostgreSQL
Redis
Celery
Authentication
```

Features:

- User accounts
- Search history
- Saved leads
- Lead status
- Team sharing
- Campaigns
- Notes
- Export
- Background jobs
- Usage tracking

---

# 39. Future Features

## CRM Integration

Export leads to:

```text
HubSpot
Salesforce
Zoho CRM
Pipedrive
```

## WhatsApp

Generate:

```text
Cold call script
WhatsApp message
Email
LinkedIn message
```

## Email Outreach

Potential workflow:

```text
Lead
 ↓
AI research
 ↓
Personalized email
 ↓
Human approval
 ↓
Send
```

Keep human approval before automated outreach.

## Lead Monitoring

Periodically re-check:

```text
New negative reviews
New website
New contact information
Rating changes
New technology signals
```

## Competitor Analysis

Compare:

```text
Business A
Business B
Business C
```

based on:

```text
digital presence
reviews
technology
customer complaints
software opportunities
```

---

# 40. Example End-to-End Execution

User enters:

```text
Location: Chennai
Category: Clothing Stores
Rating: 3.0 - 4.0
Minimum Reviews: 20
Leads: 5
```

### Step 1

Apify searches Google Maps.

```text
100 businesses found
```

### Step 2

Filter:

```text
Category = Clothing
Rating = 3.0 - 4.0
Reviews >= 20
```

```text
32 businesses remain
```

### Step 3

Rank candidates.

```text
20 candidates selected
```

### Step 4

Collect reviews.

```text
20 businesses
×
available reviews
```

### Step 5

Pre-filter reviews.

```text
500 reviews
↓
80 potentially relevant
```

### Step 6

LLM analysis.

```text
80 reviews
↓
Pain points
```

### Step 7

Website analysis.

```text
20 websites
↓
Technology signals
↓
Emails
```

### Step 8

Lead scoring.

```text
20 candidates
↓
Top 5
```

### Step 9

Generate:

```text
Business information
+
Pain points
+
Evidence
+
Software opportunity
+
Lead score
+
Sales pitch
```

### Step 10

Export:

```text
leads.csv
```

---

# 41. Example Final Lead

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ABC FASHION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Category:
Clothing Store

Rating:
3.6 / 5

Reviews:
218

Location:
Chennai

Phone:
+91 XXXXX XXXXX

Email:
info@abcfashion.com

Website:
https://example.com

Google Maps:
[Maps URL]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CUSTOMER PAIN POINT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Problem:
Long billing waiting time

Category:
POS / Billing

Severity:
High

Customer Evidence:
"Had to wait almost 30 minutes to pay."

Business Impact:
Potential customer dissatisfaction and
checkout delays.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SOFTWARE OPPORTUNITY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Recommended Solution:
Multi-counter POS + Inventory Management

Opportunity:
High

Confidence:
91%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TECHNOLOGY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Website:
Yes

E-commerce:
Yes

Payment:
Yes

WhatsApp:
Yes

Inventory visibility:
No

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LEAD SCORE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

84 / 100

Priority:
HOT

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COLD CALL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Hi, I'm calling from XYZ Technologies.

We help retail businesses improve their billing
and inventory operations. I noticed customer
feedback mentioning long waiting times during
billing, so I wanted to check whether you're
currently using a POS system that supports
multiple billing counters.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

# 42. Recommended MVP Milestone

The first target should **not** be a polished dashboard.

The first target is:

```text
Input
 ↓
Apify
 ↓
20 businesses
 ↓
Reviews
 ↓
LLM
 ↓
Top 5 qualified leads
 ↓
CSV
```

If those five leads are genuinely useful to the sales team, then build the full platform.

---

# 43. Final Recommended Architecture

For the fastest practical implementation:

```text
                USER
                  │
                  ▼
          ┌───────────────┐
          │   Streamlit   │
          │      V1       │
          └───────┬───────┘
                  │
                  ▼
          ┌───────────────┐
          │    Python     │
          │   Pipeline    │
          └───────┬───────┘
                  │
       ┌──────────┼──────────┐
       ▼          ▼          ▼
    Apify       Website    OpenAI
    Maps        Crawler      LLM
       │          │          │
       └──────────┼──────────┘
                  ▼
          ┌───────────────┐
          │ Lead Scoring  │
          └───────┬───────┘
                  ▼
          ┌───────────────┐
          │     CSV       │
          └───────────────┘
```

Then upgrade to:

```text
Next.js
    ↓
FastAPI
    ↓
Redis + Celery
    ↓
Apify + Google Places
    ↓
Website Intelligence
    ↓
OpenAI
    ↓
PostgreSQL
    ↓
Lead Dashboard + CSV + CRM
```

---

# 44. Project Positioning

Do not position this internally as:

> Google Maps Scraper

Position it as:

> **AI Lead Intelligence & Sales Prospecting Platform**

### One-line description

> An AI-powered platform that discovers local businesses, analyzes customer complaints to identify software pain points, detects technology opportunities, ranks sales prospects, and generates personalized cold-calling intelligence.

### Core value proposition

```text
Find businesses
      +
Understand their problems
      +
Identify software opportunities
      +
Prioritize the best leads
      +
Give salespeople a reason to call
```

That is the core product.
