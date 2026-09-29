with staged as (
    select * from {{ ref('stg_patients') }}
),
calculated as (
    select
        patient_id,
        mrn,
        concat(first_name, ' ', last_name) as full_name,
        gender,
        birth_date,
        timestampdiff(year, birth_date, curdate()) as age
    from staged
)

select
    patient_id,
    mrn,
    full_name,
    gender,
    birth_date,
    age,
    case
        when age is null then 'Inconnu'
        when age < 5 then '0-4 ans (Nourrisson/Enfant)'
        when age between 5 and 14 then '5-14 years old (Enfant)'
        when age between 15 and 24 then '15-24 ans (Jeune)'
        when age between 25 and 49 then '25-49 (Adulte)'
        when age between 50 and 64 then '50-64 ans (Senior)'
        when age >= 65 then '65 ans et plus (Aîné)'
        else 'Inconnu'
    end as age_group
from calculated