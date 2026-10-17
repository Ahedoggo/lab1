CREATE TABLE IF NOT EXISTS
                    lakehouse.bronze_orc.lineitem
                WITH (
                    format = 'ORC',
                    compression_codec = 'ZSTD'
                )
                AS
                SELECT orderkey, linenumber, extendedprice, discount, returnflag
                FROM tpch.sf1.lineitem;
