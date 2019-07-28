import pytest
from pydicom.dataset import Dataset, FileMetaDataset, validate_file_meta
from pydicom.uid import (
    ImplicitVRLittleEndian,
    ExplicitVRBigEndian,
    PYDICOM_IMPLEMENTATION_UID,
)


def test_group2_only():
    """FileMetaDataset class allows only group 2 tags"""
    meta = FileMetaDataset()

    # Group !=2 raises exception
    with pytest.raises(KeyError):
        meta.PatientName = "test"

    with pytest.raises(KeyError):
        meta.add_new(0x30001, "OB", "test")

    # But group 2 is allowed
    meta.ImplementationVersionName = "abc"
    meta.add_new(0x20016, "AE", "ae")


def test_file_meta_binding():
    """File_meta reference remains bound in parent Dataset"""
    # Test exists to show new FileMetaDataset still
    #   allows old-style, does not get re-bound to new FileMetaDataset
    # This ensures old code using file_meta = Dataset() will still work
    ds = Dataset()
    meta = Dataset()  # old style
    ds.file_meta = meta
    meta.ImplementationVersionName = "implem"
    assert ds.file_meta.ImplementationVersionName == "implem"


def test_access_file_meta_from_parent():
    """Accessing group2 tag in dataset gets from file_meta if exists"""
    # New in v1.4
    ds = Dataset()
    meta = Dataset()
    ds.file_meta = meta
    meta.ImplementationVersionName = "abc"

    # direct from ds, not through ds.file_meta
    assert ds.ImplementationVersionName == "abc"
    assert ds[0x00020013].value == "abc"


def test_assign_file_meta_existing_tags():
    """Dataset raises if assigning file_meta with tags already in dataset"""
    # New in v1.4
    meta = FileMetaDataset()
    ds = Dataset()

    # store element in main dataset, no file_meta for it
    ds.ImplementationVersionName = "already here"

    # Now also in meta
    meta.ImplementationVersionName = "new one"

    # conflict raises
    with pytest.raises(KeyError):
        ds.file_meta = meta


def test_assign_file_meta_moves_existing_group2():
    """Setting file_meta in a dataset moves existing group 2 elements"""
    meta = FileMetaDataset()
    ds = Dataset()

    # Set ds up with some group 2
    ds.ImplementationVersionName = "main ds"
    ds.MediaStorageSOPClassUID = "4.5.6"

    # also have something in meta
    meta.TransferSyntaxUID = "1.2.3"

    ds.file_meta = meta
    assert meta.ImplementationVersionName == "main ds"
    assert meta.MediaStorageSOPClassUID == "4.5.6"
    # and existing one unharmed
    assert meta.TransferSyntaxUID == "1.2.3"

    # And elements are no longer in main dataset
    assert "MediaStorageSOPClassUID" not in ds._dict
    assert "ImplementationVersionName" not in ds._dict


def test_assign_ds_already_in_meta_overwrites():
    meta = FileMetaDataset()
    ds = Dataset()
    ds.file_meta = meta
    # First assign in meta
    ds.file_meta.ImplementationVersionName = "imp-meta"
    ds.ImplementationVersionName = "last set"

    assert "last set" == ds.file_meta.ImplementationVersionName
    assert "last set" == ds.ImplementationVersionName


def test_file_meta_contains():
    meta = FileMetaDataset()
    ds = Dataset()
    ds.file_meta = meta

    ds.file_meta.ImplementationVersionName = "implem"
    assert "ImplementationVersionName" in ds.file_meta
    assert "ImplementationVersionName" in ds


def test_file_meta_del():
    meta = FileMetaDataset()
    ds = Dataset()
    ds.file_meta = meta
    ds.file_meta.ImplementationVersionName = "implem"
    del ds.file_meta.ImplementationVersionName
    assert "ImplementationVersionName" not in ds    
    assert "ImplementationVersionName" not in ds

    ds.file_meta.ImplementationVersionName = "implem2"
    del ds.ImplementationVersionName
    assert "ImplementationVersionName" not in ds    
    assert "ImplementationVersionName" not in ds


class TestFileMetaDataset(object):
    """Test valid file meta behavior"""

    def setup(self):
        self.ds = Dataset()
        self.sub_ds1 = Dataset()
        self.sub_ds2 = Dataset()

    def test_ensure_file_meta(self):
        assert not hasattr(self.ds, "file_meta")
        self.ds.ensure_file_meta()
        assert hasattr(self.ds, "file_meta")
        assert not self.ds.file_meta

    def test_fix_meta_info(self):
        self.ds.is_little_endian = True
        self.ds.is_implicit_VR = True
        self.ds.fix_meta_info(enforce_standard=False)
        assert ImplicitVRLittleEndian == self.ds.file_meta.TransferSyntaxUID

        self.ds.is_implicit_VR = False
        self.ds.fix_meta_info(enforce_standard=False)
        # transfer syntax does not change because of ambiguity
        assert ImplicitVRLittleEndian == self.ds.file_meta.TransferSyntaxUID

        self.ds.is_little_endian = False
        self.ds.is_implicit_VR = True
        with pytest.raises(NotImplementedError):
            self.ds.fix_meta_info()

        self.ds.is_implicit_VR = False
        self.ds.fix_meta_info(enforce_standard=False)
        assert ExplicitVRBigEndian == self.ds.file_meta.TransferSyntaxUID

        assert "MediaStorageSOPClassUID" not in self.ds.file_meta
        assert "MediaStorageSOPInstanceUID " not in self.ds.file_meta
        with pytest.raises(ValueError, match="Missing required File Meta .*"):
            self.ds.fix_meta_info(enforce_standard=True)

        self.ds.SOPClassUID = "1.2.3"
        self.ds.SOPInstanceUID = "4.5.6"
        self.ds.fix_meta_info(enforce_standard=False)
        assert "1.2.3" == self.ds.file_meta.MediaStorageSOPClassUID
        assert "4.5.6" == self.ds.file_meta.MediaStorageSOPInstanceUID
        self.ds.fix_meta_info(enforce_standard=True)

    def test_validate_and_correct_file_meta(self):
        file_meta = FileMetaDataset()
        validate_file_meta(file_meta, enforce_standard=False)
        with pytest.raises(ValueError):
            validate_file_meta(file_meta, enforce_standard=True)

        file_meta = FileMetaDataset()
        file_meta.MediaStorageSOPClassUID = "1.2.3"
        file_meta.MediaStorageSOPInstanceUID = "1.2.4"
        # still missing TransferSyntaxUID
        with pytest.raises(ValueError):
            validate_file_meta(file_meta, enforce_standard=True)

        file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        validate_file_meta(file_meta, enforce_standard=True)

        # check the default created values
        assert b"\x00\x01" == file_meta.FileMetaInformationVersion
        assert PYDICOM_IMPLEMENTATION_UID == file_meta.ImplementationClassUID
        assert file_meta.ImplementationVersionName.startswith("PYDICOM ")

        file_meta.ImplementationClassUID = "1.2.3.4"
        file_meta.ImplementationVersionName = "ACME LTD"
        validate_file_meta(file_meta, enforce_standard=True)
        # check that existing values are left alone
        assert "1.2.3.4" == file_meta.ImplementationClassUID
        assert "ACME LTD" == file_meta.ImplementationVersionName
