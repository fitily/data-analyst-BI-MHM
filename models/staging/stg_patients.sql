
{{ config(materialized='table') }}
with raw_patients as (
    select *
    from {{ source('prod_mhm_ps', 'patients')}}
    where coalesce(deleted, 0) = 0
),

cleaned as (
    select
        id as patient_id,
        mrn,
        trim(firstName) as first_name,
        trim(lastName) as last_name,
        str_to_date(birthDate, '%Y-%m-%d') as birth_date,
        case
            when trim(upper(gender)) in ('M', '1') then 'Homme'
            when trim(upper(gender)) in ('F') then 'Femme'
            else 'non renseigné'
        end as gender,

        upper(trim(coalesce(nullif(nullif(raw_patients.district, ''), 'INCONNU'), cleaned_location.district, 'INCONNU'))) as district,
        upper(trim(coalesce(nullif(nullif(raw_patients.commune, ''), 'INCONNU'), cleaned_location.commune, 'INCONNU'))) as commune,
        upper(trim(coalesce(nullif(nullif(raw_patients.fonkontany, ''), 'INCONNU'), cleaned_location.fonkontany, 'INCONNU'))) as fonkontany,
        created_at
    from raw_patients
    left join {{ ref('seed_patients_adresses_cleaned') }} as cleaned_location
        on convert(cleaned_location.patient_id using utf8mb4) collate utf8mb4_unicode_ci
         = convert(raw_patients.id using utf8mb4) collate utf8mb4_unicode_ci
)

select * from cleaned
