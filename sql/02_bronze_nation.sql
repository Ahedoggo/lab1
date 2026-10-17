CREATE TABLE IF NOT EXISTS
                    lakehouse.bronze.nation
                WITH (
                    format = 'PARQUET',
                    compression_codec = 'ZSTD'
                )
                AS
                SELECT nationkey, name
                FROM tpch.sf1.nation;
