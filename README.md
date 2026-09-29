# MHM Patient Demographics Analytics

## 📌 Overview

This project is a **dbt-based analytical data transformation pipeline** developed during an academic internship at **MHM**, a health-focused NGO.

The objective is to transform patient data from a **MariaDB operational database** into structured analytical models for demographic analysis and business intelligence.

The main business use case is:

> **Analyzing the distribution of patients by age group, gender, and place of residence.**

The geographic analysis is performed at three levels:

* Fokontany
* Commune
* District

---

## 🎯 Business Objective

The analytical model is designed to answer questions such as:

* How are patients distributed by age group?
* What is the distribution of patients by gender?
* How many patients are registered in each district?
* How are patients distributed across communes?
* How are patients distributed across fokontany?
* How does the demographic distribution vary by geographic area?

### Main analytical dimensions

```text
Demographics
├── Age
├── Age group
└── Gender

Geography
├── District
├── Commune
└── Fokontany
```

---

## 🏗️ Architecture

```text
                         ┌──────────────────────┐
                         │       MariaDB        │
                         │  Operational Source  │
                         │       patients       │
                         └──────────┬───────────┘
                                    │
                              dbt source()
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │    stg_patients      │
                         │       STAGING        │
                         └──────────┬───────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
                    ▼                               ▼
          ┌──────────────────┐             ┌──────────────────┐
          │   dim_patients   │             │  dim_locations   │
          │                  │             │                  │
          │ age              │             │ district         │
          │ age_group        │             │ commune          │
          │ gender           │             │ fokontany        │
          └────────┬─────────┘             └────────┬─────────┘
                   │                                │
                   └───────────────┬────────────────┘
                                   ▼
                     ┌─────────────────────────┐
                     │ fct_patient_demographics│
                     │                         │
                     │ patient_id              │
                     │ location_id             │
                     │ gender                  │
                     │ age                     │
                     │ age_group               │
                     │ patient_count           │
                     └────────────┬────────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │    Metabase     │
                         │       BI        │
                         └────────┬────────┘
                                  │
                                  ▼
                   Patient Demographics Analysis
```

---

## 🔄 Data Transformation Pipeline

### 1. Source — MariaDB

The project uses a MariaDB operational database as its source.

The `patients` table is declared as a dbt source and referenced using:

```sql
{{ source('prod_mhm_ps', 'patients') }}
```

The raw operational data is not included in this repository.

---

### 2. Staging — `stg_patients`

The staging model prepares the source data for analytical modeling.

The main transformations include:

* filtering records marked as deleted
* trimming patient names
* converting birth dates
* standardizing gender values
* standardizing geographic information
* handling missing geographic values
* integrating cleaned address information from a dbt seed
* renaming source columns using analytical naming conventions

For example, gender values are standardized into:

```text
M / 1 → Homme
F    → Femme
Other / missing → non renseigné
```

Geographic information is standardized at three levels:

```text
District
   ↓
Commune
   ↓
Fokontany
```

---

## 👤 Patient Dimension — `dim_patients`

The `dim_patients` model provides patient demographic attributes for analytical use.

Main attributes include:

```text
patient_id
mrn
full_name
gender
birth_date
age
age_group
```

### Age calculation

Age is calculated from the patient's birth date:

```sql
timestampdiff(year, birth_date, curdate())
```

The calculated age is then grouped into analytical categories:

|     Age | Age group      |
| ------: | -------------- |
|     < 5 | 0-4 ans        |
|    5–14 | 5-14 years old |
|   15–24 | 15-24 ans      |
|   25–49 | 25-49          |
|   50–64 | 50-64 ans      |
|     65+ | 65 ans et plus |
| Missing | Inconnu        |

These groups facilitate demographic reporting and visualization.

---

## 📍 Location Dimension — `dim_locations`

The `dim_locations` model creates a distinct geographic dimension.

The geographic hierarchy is:

```text
District
   ↓
Commune
   ↓
Fokontany
```

A `location_id` is generated from the combination of:

```text
district + commune + fokontany
```

using an MD5 hash.

This provides a unique identifier for each geographic combination used in the analytical model.

---

## 📊 Fact Table — `fct_patient_demographics`

The `fct_patient_demographics` model is the main analytical fact table.

### Grain

> **One row represents one patient.**

The fact table contains:

```text
patient_id
location_id
gender
age
age_group
patient_count
```

The `patient_count` field is set to:

```sql
1 as patient_count
```

This allows patient counts to be calculated by aggregating:

```sql
SUM(patient_count)
```

For example, the same fact table can be used to calculate:

```text
Total patients
        ↓
By gender
        ↓
By age group
        ↓
By district
        ↓
By commune
        ↓
By fokontany
```

The combination of these attributes also enables multidimensional demographic analysis.

---

## 📈 Business Intelligence

The analytical models can be connected to **Metabase** to create dashboards and reports.

Potential visualizations include:

### Patient distribution by age group

```text
Age group → Number of patients
```

### Patient distribution by gender

```text
Gender → Number of patients
```

### Patient distribution by district

```text
District → Number of patients
```

### Patient distribution by commune

```text
Commune → Number of patients
```

### Patient distribution by fokontany

```text
Fokontany → Number of patients
```

The dimensions can also be combined, for example:

```text
District
   ↓
Commune
   ↓
Fokontany

combined with:

Age group
Gender
```

This allows more detailed demographic and geographic analysis.

---

## 🛠️ Technologies

* **MariaDB** — operational source database
* **dbt** — data transformation and analytical modeling
* **SQL** — data transformation and querying
* **Python** — data preparation and cleaning
* **Docker** — development environment
* **Metabase** — business intelligence and visualization
* **Git / GitHub** — version control and project documentation

---

## 📁 Project Structure

```text
.
├── models/
│   ├── staging/
│   │   ├── _sources.yml
│   │   └── stg_patients.sql
│   │
│   └── marts/
│       ├── dim_locations.sql
│       ├── dim_patients.sql
│       └── fct_patient_demographics.sql
│
├── scripts/
│   └── data_cleaning.py
│
├── Dockerfile
├── docker-compose.yml
├── dbt_project.yml
├── profiles.yml.example
├── .gitignore
└── README.md
```

---

## 🔐 Data Privacy

This repository does **not contain real patient data or confidential health information**.

Operational datasets and sensitive records are excluded from version control.

The repository focuses on:

* transformation logic
* data modeling
* analytical methodology
* project architecture
* reproducible code structure

---

## 📚 Skills Demonstrated

This project demonstrates practical experience with:

* SQL
* dbt
* Data transformation
* Data cleaning
* Data modeling
* Dimensional modeling
* Demographic analysis
* Geographic analysis
* MariaDB
* Python
* Docker
* Business Intelligence
* Metabase
* Git and GitHub

---

## 🚀 Future Improvements

Possible extensions include:

* adding dbt data quality tests
* documenting models and columns with dbt
* improving geographic data quality
* adding additional demographic indicators
* implementing data freshness monitoring
* developing a complete Metabase dashboard
* adding automated dbt documentation
* extending the analytical model to additional business requirements

---

## 👤 Author

**Miandry Finiavana Anjaramandresy**

Master's student in Artificial Intelligence and Data Science
ENI – University of Fianarantsoa

GitHub: https://github.com/fitily