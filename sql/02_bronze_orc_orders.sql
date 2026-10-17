CREATE TABLE IF NOT EXISTS
                    lakehouse.bronze_orc.orders
                WITH (
                    format = 'ORC',
                    compression_codec = 'ZSTD'
                )
                AS
                SELECT orderkey, custkey, orderdate
                FROM tpch.sf1.orders;
