-- Snapshot ID необходимо получать перед повторным запуском.
            
        INSERT INTO lakehouse.silver.evolution_demo
        VALUES (-1, 'temporary row', 'demo')
    ;

            
        SELECT count(*)
        FROM lakehouse.silver.evolution_demo
        FOR VERSION AS OF 8827974259937155893
    ;

            
        ALTER TABLE lakehouse.silver.evolution_demo
        EXECUTE rollback_to_snapshot(8827974259937155893);
