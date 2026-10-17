SELECT count(*) - count(DISTINCT custkey)
            FROM lakehouse.bronze.customer;

SELECT count(*) - count(DISTINCT orderkey)
            FROM lakehouse.bronze.orders;

SELECT count(*)
            FROM (
                SELECT orderkey, linenumber
                FROM lakehouse.bronze.lineitem
                GROUP BY orderkey, linenumber
                HAVING count(*) > 1
            );

SELECT count(*)
            FROM lakehouse.bronze.lineitem
            WHERE extendedprice IS NULL
               OR extendedprice < 0
               OR discount IS NULL
               OR discount NOT BETWEEN 0 AND 1;

SELECT count(*)
            FROM lakehouse.bronze.orders AS o
            LEFT JOIN lakehouse.bronze.customer AS c
                ON o.custkey = c.custkey
            WHERE c.custkey IS NULL;

SELECT count(*)
            FROM lakehouse.bronze.lineitem AS l
            LEFT JOIN lakehouse.bronze.orders AS o
                ON o.orderkey = l.orderkey
            WHERE o.orderkey IS NULL;

SELECT count(*)
            FROM lakehouse.bronze.customer AS c
            LEFT JOIN lakehouse.bronze.nation AS n
                ON n.nationkey = c.nationkey
            WHERE n.nationkey IS NULL;
