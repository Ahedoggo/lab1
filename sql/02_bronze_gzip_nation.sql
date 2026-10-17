CREATE TABLE IF NOT EXISTS
                    lakehouse.bronze_gzip.nation
                WITH (
                    format = 'PARQUET',
                    compression_codec = 'GZIP'
                )
                AS
                SELECT nationkey, name
                FROM tpch.sf1.nation;
