CREATE TABLE IF NOT EXISTS
                    lakehouse.silver.customer_dim
                WITH (
                    format = 'PARQUET',
                    compression_codec = 'ZSTD'
                )
                AS
                SELECT
                    c.custkey,
                    c.name,
                    c.acctbal,
                    n.name AS nation,
                    c.address,
                    c.phone,
                    c.comment,
                    trim(c.name) AS name_normalized,
                    trim(c.address) AS address_normalized,
                    trim(c.comment) AS comment_normalized
                FROM lakehouse.bronze.customer AS c
                JOIN lakehouse.bronze.nation AS n
                    ON c.nationkey = n.nationkey
                WHERE c.custkey IS NOT NULL;
