import os
import uuid

import mpld3 as mpld3
import wtforms
from flask import Flask, render_template, request, redirect, url_for

from jacks.io_preprocess import loadJacksFullResultsFromPickle, getSortedGenes, getGeneWs
from plot_heatmap import plot_heatmap
from run_JACKS import run_jacks, pickle_filename, rep_hdr_default, sample_hdr_default, ctrl_sample_or_hdr_default, \
    sgrna_hdr_default, gene_hdr_default, outprefix_default, apply_w_hp_default

app = Flask(__name__, template_folder="templates")
app.config['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'

# @celery.task(bind=True)
def send_to_jacks(countfile, replicatefile, guidemappingfile,
                  rep_hdr, sample_hdr, ctrl_sample_or_hdr,
                  sgrna_hdr, gene_hdr,
                  outprefix, reffile):
    run_jacks(countfile, replicatefile, guidemappingfile,
              rep_hdr, sample_hdr, ctrl_sample_or_hdr,
              sgrna_hdr, gene_hdr,
              outprefix, reffile=reffile)
    # return analysis_id
    # self.update_state(state='PROGRESS',
    #                   meta={'current': i, 'total': total,
    #                         'status': message})
    #     time.sleep(1)
    # return {'current': 100, 'total': 100, 'status': 'Task completed!',
    #         'result': 42}


def get_pickle_file(analysis_id):
    return os.path.join("results", analysis_id, pickle_filename)

class JacksForm(wtforms.Form):
    raw_count_file = wtforms.FileField('Raw count file', default="examples/example_co")
    replicate_map_file = wtforms.FileField('Replicate map field')
    header_replicates = wtforms.StringField('Header for replicates')
    header_sample = wtforms.StringField('Header for sample')
    ctrl_sample_name = wtforms.StringField('Name for a control sample')
    grna_gene_map_file = wtforms.FileField('gRNA-Gene map file')
    header_grna = wtforms.StringField('Header for gRNA id')
    header_gene = wtforms.StringField('Header for Gene')
    use_reference_lib = wtforms.RadioField('Use reference library', choices=[('ref', 'Use reference library'),
                                                                             ('none', 'No reference')])
    reference_lib = wtforms.SelectField('Reference library', choices=[("", 'None'),
                                                                      ('yusav1.0', 'Yusa v1.0'),
                                                                      ('yusav1.1', 'Yusa v1.1'),
                                                                      ('avana', 'Avana'),
                                                                      ('brunello', 'Brunello'),
                                                                      ('whitehead', 'Whitehead'),
                                                                      ('toronto', 'Toronto Knockout')])
    max_genes_display = wtforms.IntegerField('Max genes to display', default=20)


@app.route('/')
def hello():
    return redirect(url_for('start_analysis'))


@app.route('/JACKS', methods=["GET", "POST"])
def start_analysis():
    template = "index.html"
    form = JacksForm(request.form)
    if request.method == 'POST':
        raw_count_file = form.raw_count_file.data
        replicate_map_file = form.replicate_map_file.data
        header_replicates = form.header_replicates.data
        header_sample = form.header_sample.data
        ctrl_sample_name = form.ctrl_sample_name.data
        grna_gene_map_file = form.grna_gene_map_file.data
        header_grna = form.header_grna.data
        header_gene = form.header_gene.data
        reference_lib = form.reference_lib.data
        if not raw_count_file:
            raw_count_file = grna_gene_map_file = "jacks/example-small/example_count_data.tab"
            replicate_map_file = "jacks/example-small/example_repmap.tab"
            reference_lib = None
            header_grna = sgrna_hdr_default
            header_gene = 'gene'
            header_sample = sample_hdr_default
            header_replicates = rep_hdr_default
            ctrl_sample_name = 'CTRL'

        analysis_id = str(uuid.uuid4()).replace("-", "")[:12] + "/"
        send_to_jacks(countfile=raw_count_file, replicatefile=replicate_map_file, guidemappingfile=grna_gene_map_file,
                      rep_hdr=header_replicates, sample_hdr=header_sample, ctrl_sample_or_hdr=ctrl_sample_name,
                      sgrna_hdr=header_grna, gene_hdr=header_gene, outprefix="results/" + analysis_id, reffile=reference_lib)
        return render_template(template, form=form, analysis_id=analysis_id)
    return render_template(template, form=form)


@app.route('/results/<analysis_id>', methods=["GET"])
def retrieve_results(analysis_id):
    template = "results.html"
    jacks_results, cell_lines, gene_grnas = loadJacksFullResultsFromPickle(get_pickle_file(analysis_id))
    table = []
    sorted_genes = getSortedGenes(jacks_results)
    for gene in sorted_genes:
        row = [gene[1], gene[0]]
        row.extend(getGeneWs(jacks_results, gene[1]))
        table.append(row)
    return render_template(template, table=table, cell_lines=cell_lines)


@app.route('/results/<analysis_id>/gene/<gene>', methods=["GET"])
def plot_gene_heatmap(analysis_id, gene):
    template = "plot.html"
    picklefile = get_pickle_file(analysis_id)
    if os.path.isfile(picklefile):
        image_path = os.path.join("server", "static", "results", analysis_id, "figure.png")
        plot_heatmap(picklefile, gene, image_path)
        return render_template(template, image_path=image_path.replace("server", ""))
    else:
        return render_template(template)

if __name__ == '__main__':
    app.run()
