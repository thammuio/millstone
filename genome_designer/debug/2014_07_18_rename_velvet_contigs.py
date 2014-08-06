import os
import shutil

from main.models import *

ag = AlignmentGroup.objects.get(uid='edc74a3d')

for etsa in ag.experimentsampletoalignment_set.all():
    sample_label = etsa.experiment_sample.label
    velvet_dir = os.path.join(etsa.get_model_data_dir(), 'velvet')
    contigs_file = os.path.join(velvet_dir, 'contigs.fa')
    copy_dest = os.path.join(velvet_dir, sample_label + '.fa')

    # Copy file
    # shutil.copyfile(contigs_file, copy_dest)

    print copy_dest


