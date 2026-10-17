CREATE TABLE IF NOT EXISTS
                    lakehouse.bronze.customer
                WITH (
                    format = 'PARQUET',
                    compression_codec = 'ZSTD'
                )
                AS
                SELECT custkey, name, acctbal, nationkey, address, phone, comment
                FROM tpch.sf1.customer;
