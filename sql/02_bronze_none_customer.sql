CREATE TABLE IF NOT EXISTS
                    lakehouse.bronze_none.customer
                WITH (
                    format = 'PARQUET',
                    compression_codec = 'NONE'
                )
                AS
                SELECT custkey, name, acctbal, nationkey, address, phone, comment
                FROM tpch.sf1.customer;
