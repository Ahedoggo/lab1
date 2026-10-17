CREATE TABLE IF NOT EXISTS
                    lakehouse.bronze_none.orders
                WITH (
                    format = 'PARQUET',
                    compression_codec = 'NONE'
                )
                AS
                SELECT orderkey, custkey, orderdate
                FROM tpch.sf1.orders;
