with patients as (
    select *
    from {{ ref('dim_patients') }}
),

staged_patients as (
    select *
    from {{ ref('stg_patients') }}
),

locations as (
    select *
    from {{ ref('dim_locations') }}
)

select
    p.patient_id,
    l.location_id,
    p.gender,
    p.age,
    p.age_group,
    1 as patient_count
from patients p
join staged_patients sp
    on p.patient_id = sp.patient_id
left join locations l
    on sp.district = l.district
    and sp.commune = l.commune
    and sp.fonkontany = l.fonkontany
