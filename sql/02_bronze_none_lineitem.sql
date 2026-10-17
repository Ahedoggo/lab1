CREATE TABLE IF NOT EXISTS
                    lakehouse.bronze_none.lineitem
                WITH (
                    format = 'PARQUET',
                    compression_codec = 'NONE'
                )
                AS
                SELECT orderkey, linenumber, extendedprice, discount, returnflag
                FROM tpch.sf1.lineitem;
