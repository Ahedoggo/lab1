CREATE TABLE IF NOT EXISTS
                    lakehouse.bronze_gzip.orders
                WITH (
                    format = 'PARQUET',
                    compression_codec = 'GZIP'
                )
                AS
                SELECT orderkey, custkey, orderdate
                FROM tpch.sf1.orders;
