CREATE TABLE IF NOT EXISTS
                    lakehouse.bronze_none.nation
                WITH (
                    format = 'PARQUET',
                    compression_codec = 'NONE'
                )
                AS
                SELECT nationkey, name
                FROM tpch.sf1.nation;
