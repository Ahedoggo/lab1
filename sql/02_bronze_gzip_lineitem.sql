CREATE TABLE IF NOT EXISTS
                    lakehouse.bronze_gzip.lineitem
                WITH (
                    format = 'PARQUET',
                    compression_codec = 'GZIP'
                )
                AS
                SELECT orderkey, linenumber, extendedprice, discount, returnflag
                FROM tpch.sf1.lineitem;
