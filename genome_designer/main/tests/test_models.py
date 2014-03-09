"""
Tests for models.py.
"""

import json
import os

from django.conf import settings
from django.test import TestCase

from main.models import AlignmentGroup
from main.models import Dataset
from main.models import ExperimentSample
from main.models import ExperimentSampleToAlignment
from main.models import Project
from main.models import ReferenceGenome
from main.models import User
from main.models import Variant
from main.models import VariantCallerCommonData
from main.model_utils import clean_filesystem_location
from main.model_utils import get_dataset_with_type
from scripts.import_util import import_reference_genome_from_local_file
import subprocess


TEST_USERNAME = 'testuser'
TEST_PASSWORD = 'password'
TEST_EMAIL = 'test@example.com'
TEST_PROJECT_NAME = 'testModels_project'
TEST_REF_GENOME_NAME = 'mg1655_partial'
TEST_REF_GENOME_PATH = os.path.join(settings.PWD,
    'test_data/full_vcf_test_set/mg1655_tolC_through_zupT.gb')


class TestModels(TestCase):

    def setUp(self):
        """Override.
        """
        user = User.objects.create_user(TEST_USERNAME, password=TEST_PASSWORD,
                email=TEST_EMAIL)

        self.test_project = Project.objects.create(
            title=TEST_PROJECT_NAME,
            owner=user.get_profile())

        self.test_ref_genome = import_reference_genome_from_local_file(
            self.test_project,
            TEST_REF_GENOME_NAME,
            TEST_REF_GENOME_PATH,
            'genbank')


    def test_snpeff_on_create_ref_genome(self):
        """Ensure that Snpeff database is created successfully when creating
           a new reference genome object.
        """

        # check that the genbank file was symlinked
        assert os.path.exists(os.path.join(
                self.test_ref_genome.get_snpeff_directory_path(),
                'genes.gb'))

        # check that the db was made
        assert os.path.exists(os.path.join(
                self.test_ref_genome.get_snpeff_directory_path(),
                'snpEffectPredictor.bin'))


class TestAlignmentGroup(TestCase):

    def test_get_samples(self):
        user = User.objects.create_user(TEST_USERNAME, password=TEST_PASSWORD,
                email=TEST_EMAIL)
        self.test_project = Project.objects.create(
                title=TEST_PROJECT_NAME,
                owner=user.get_profile())
        self.test_ref_genome = ReferenceGenome.objects.create(
                project=self.test_project,
                label='blah',
                num_chromosomes=1,
                num_bases=1000)
        alignment_group = AlignmentGroup.objects.create(
            label='Alignment 1',
            reference_genome=self.test_ref_genome,
            aligner=AlignmentGroup.ALIGNER.BWA)

        # Create a bunch of samples and relate them.
        for sample_idx in range(10):
            sample = ExperimentSample.objects.create(
                    uid=str(sample_idx),
                    project=self.test_project,
                    label='some label'
            )
            ExperimentSampleToAlignment.objects.create(
                    alignment_group=alignment_group,
                    experiment_sample=sample)

        # Test the method.
        samples = alignment_group.get_samples()
        sample_uid_set = set([sample.uid for sample in samples])
        self.assertEqual(sample_uid_set,
                set([str(x) for x in range(10)]))


class TestDataset(TestCase):

    def test_get_related_model_set(self):
        user = User.objects.create_user(TEST_USERNAME, password=TEST_PASSWORD,
                email=TEST_EMAIL)
        self.test_project = Project.objects.create(
                title=TEST_PROJECT_NAME,
                owner=user.get_profile())
        self.test_ref_genome = ReferenceGenome.objects.create(
                project=self.test_project,
                label='blah',
                num_chromosomes=1,
                num_bases=1000)
        alignment_group = AlignmentGroup.objects.create(
            label='Alignment 1',
            reference_genome=self.test_ref_genome,
            aligner=AlignmentGroup.ALIGNER.BWA)
        dataset = Dataset.objects.create(
            label='the label', type=Dataset.TYPE.VCF_FREEBAYES)
        alignment_group.dataset_set.add(dataset)

        alignment_group_set = dataset.get_related_model_set()
        self.assertTrue(alignment_group in alignment_group_set.all())

    def test_dataset_compression_piping(self):
        """
        Make sure data set compression behaves correctly.
        """
        dataset = Dataset.objects.create(
                label='test_dataset', 
                type=Dataset.TYPE.FASTQ1)

        GZIPPED_FASTQ_FILEPATH = os.path.join(settings.PWD, 'test_data',
                'compressed_fastq', 'sample0.simLibrary.1.fq.gz')

        dataset.filesystem_location = clean_filesystem_location(
                    GZIPPED_FASTQ_FILEPATH)

        assert dataset.is_compressed()

        process = subprocess.Popen(
                ('head '+dataset.wrap_if_compressed()+' | wc -l'), 
                shell=True, executable=settings.BASH_PATH, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)

        wc_output, errmsg = process.communicate()
        rc = process.returncode

        assert rc == 0, (
        "Compression process returned non-zero exit status: %s" % (
                errmsg))

        assert int(wc_output) == 10, (
                "Compression failed: %s" % (errmsg))

    def test_compress_dataset(self):
        """
        Make sure that compressing a dataset and putting a new dataset
        entry into the db works correctly. 
        """
        user = User.objects.create_user(TEST_USERNAME, password=TEST_PASSWORD,
                email=TEST_EMAIL)

        self.test_project = Project.objects.create(
            title=TEST_PROJECT_NAME,
            owner=user.get_profile())

        self.test_ref_genome = import_reference_genome_from_local_file(
            self.test_project,
            TEST_REF_GENOME_NAME,
            TEST_REF_GENOME_PATH,
            'genbank')

        dataset = get_dataset_with_type(self.test_ref_genome,
                type= Dataset.TYPE.REFERENCE_GENOME_GENBANK)

        # All the magic happens here
        compressed_dataset = dataset.make_compressed('.gz')

        # Grab the new compressed dataset through the ref genome to 
        # make sure that it got added
        compressed_dataset_through_ref_genome = get_dataset_with_type(
                entity= self.test_ref_genome, 
                type= Dataset.TYPE.REFERENCE_GENOME_GENBANK,
                compressed= True)
        assert compressed_dataset == compressed_dataset_through_ref_genome



class TestModelsStatic(TestCase):
    """Tests for static methods.
    """

    def test_clean_filesystem_location(self):
        FAKE_ABS_ROOT = '/root/of/all/evil'
        EXPECTED_CLEAN_URL = 'projects/blah'
        dirty_full_url = os.path.join(FAKE_ABS_ROOT, settings.MEDIA_ROOT,
                EXPECTED_CLEAN_URL)
        clean_location = clean_filesystem_location(dirty_full_url)
        self.assertEqual(EXPECTED_CLEAN_URL, clean_location)


class TestVariantCallerCommonData(TestCase):

    def test_json_data_field(self):
        """Tests the data field which uses the Postgresql 9.3 json type.
        """
        user = User.objects.create_user(TEST_USERNAME, password=TEST_PASSWORD,
                email=TEST_EMAIL)

        test_project = Project.objects.create(
            title=TEST_PROJECT_NAME,
            owner=user.get_profile())

        reference_genome = ReferenceGenome.objects.create(
            project=test_project,
            label='ref1',
            num_chromosomes=1,
            num_bases=1000)

        variant = Variant.objects.create(
            reference_genome=reference_genome,
            type='UNKNOWN',
            chromosome='c1',
            position=100,
            ref_value='A'
        )

        raw_data_dict = {
            'key1': 'val1',
            'key2': 'val2',
        }

        # Test storing as dictionary.
        vccd = VariantCallerCommonData.objects.create(
            variant=variant,
            source_dataset_id=1,
            data=raw_data_dict
        )
        vccd_lookup = VariantCallerCommonData.objects.get(
            id=vccd.id)
        self.assertEquals(raw_data_dict, vccd_lookup.data)

        # Test storing as string.
        vccd = VariantCallerCommonData.objects.create(
            variant=variant,
            source_dataset_id=1,
            data=json.dumps(raw_data_dict)
        )
        vccd_lookup = VariantCallerCommonData.objects.get(
            id=vccd.id)
        self.assertEquals(raw_data_dict, vccd_lookup.data)

        # Test blank value.
        vccd = VariantCallerCommonData.objects.create(
            variant=variant,
            source_dataset_id=1,
        )
        self.assertEquals(0, len(vccd.data))

        # Test assigning after initial create.
        vccd = VariantCallerCommonData.objects.create(
            variant=variant,
            source_dataset_id=1,
        )
        vccd.data=json.dumps(raw_data_dict)
        vccd.save()
        vccd_lookup = VariantCallerCommonData.objects.get(
            id=vccd.id)
        self.assertEquals(raw_data_dict, vccd_lookup.data)
