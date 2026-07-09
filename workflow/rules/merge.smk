rule merge:
	input:

	output:

    log:
        "logs/merge/merge.log"
    params:

    conda:
        "../envs/python.yaml"
    script:
        "../scripts/merge/merge.py"