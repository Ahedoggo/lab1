CREATE TABLE IF NOT EXISTS
                    lakehouse.bronze.lineitem
                WITH (
                    format = 'PARQUET',
                    compression_codec = 'ZSTD'
                )
                AS
                SELECT orderkey, linenumber, extendedprice, discount, returnflag
                FROM tpch.sf1.lineitem;
