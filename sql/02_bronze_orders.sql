CREATE TABLE IF NOT EXISTS
                    lakehouse.bronze.orders
                WITH (
                    format = 'PARQUET',
                    compression_codec = 'ZSTD'
                )
                AS
                SELECT orderkey, custkey, orderdate
                FROM tpch.sf1.orders;
