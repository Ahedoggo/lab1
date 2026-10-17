CREATE TABLE IF NOT EXISTS
                    lakehouse.bronze_orc.customer
                WITH (
                    format = 'ORC',
                    compression_codec = 'ZSTD'
                )
                AS
                SELECT custkey, name, acctbal, nationkey, address, phone, comment
                FROM tpch.sf1.customer;
