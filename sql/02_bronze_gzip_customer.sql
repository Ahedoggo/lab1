CREATE TABLE IF NOT EXISTS
                    lakehouse.bronze_gzip.customer
                WITH (
                    format = 'PARQUET',
                    compression_codec = 'GZIP'
                )
                AS
                SELECT custkey, name, acctbal, nationkey, address, phone, comment
                FROM tpch.sf1.customer;
