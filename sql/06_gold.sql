CREATE TABLE IF NOT EXISTS
                    lakehouse.gold.returned_customers_top20
                WITH (
                    format = 'PARQUET',
                    compression_codec = 'ZSTD'
                )
                AS
                SELECT
                    c.custkey,
                    c.name,
                    sum(l.revenue) AS revenue,
                    c.acctbal,
                    c.nation,
                    c.address,
                    c.phone,
                    c.comment
                FROM lakehouse.silver.customer_dim AS c
                JOIN lakehouse.silver.returned_lines AS l
                    ON c.custkey = l.custkey
                GROUP BY
                    c.custkey,
                    c.name,
                    c.acctbal,
                    c.nation,
                    c.address,
                    c.phone,
                    c.comment
                ORDER BY
                    revenue DESC,
                    c.custkey
                LIMIT 20;
