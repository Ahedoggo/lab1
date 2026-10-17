CREATE TABLE IF NOT EXISTS
                    lakehouse.bronze_orc.nation
                WITH (
                    format = 'ORC',
                    compression_codec = 'ZSTD'
                )
                AS
                SELECT nationkey, name
                FROM tpch.sf1.nation;
