with locations as (
    select distinct
        district, 
        commune, 
        fonkontany
    from {{ ref('stg_patients') }}
)

select
    md5(concat(district, '-', commune, '-', fonkontany)) as location_id,
    district,
    commune,
    fonkontany
from locations