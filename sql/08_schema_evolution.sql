CREATE TABLE lakehouse.silver.evolution_demo
        WITH (
            format = 'PARQUET',
            compression_codec = 'ZSTD'
        )
        AS
        SELECT
            custkey,
            name
        FROM lakehouse.silver.customer_dim
        LIMIT 3
    ;


        ALTER TABLE lakehouse.silver.evolution_demo
        ADD COLUMN source VARCHAR
    ;


        ALTER TABLE lakehouse.silver.evolution_demo
        RENAME COLUMN source TO data_source;
