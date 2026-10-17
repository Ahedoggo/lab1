CREATE TABLE IF NOT EXISTS
                    lakehouse.silver.returned_lines
                WITH (
                    format = 'PARQUET',
                    compression_codec = 'ZSTD'
                )
                AS
                SELECT
                    o.custkey,
                    o.orderkey,
                    l.linenumber,
                    o.orderdate,
                    l.extendedprice,
                    l.discount,
                    l.extendedprice * (1 - l.discount) AS revenue
                FROM lakehouse.bronze.orders AS o
                JOIN lakehouse.bronze.lineitem AS l
                    ON l.orderkey = o.orderkey
                WHERE o.orderdate >= DATE '1993-10-01'
                  AND o.orderdate < DATE '1994-01-01'
                  AND upper(trim(l.returnflag)) = 'R'
                  AND l.extendedprice >= 0
                  AND l.discount BETWEEN 0 AND 1;
