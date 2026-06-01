package cc.agentcook.application.usecase;

import cc.agentcook.application.exception.DuplicatePluginException;
import cc.agentcook.application.exception.InvalidPluginPackageException;
import cc.agentcook.application.port.in.RegisterPluginCommand;
import cc.agentcook.domain.plugin.Plugin;
import cc.agentcook.domain.plugin.PluginKind;
import cc.agentcook.domain.plugin.PluginRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.Optional;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class RegisterPluginUseCaseImplTest {

    @Mock private PluginRepository pluginRepository;
    @InjectMocks private RegisterPluginUseCaseImpl useCase;

    private static byte[] zipWithManifest(String manifestJson) throws IOException {
        ByteArrayOutputStream buf = new ByteArrayOutputStream();
        try (ZipOutputStream zos = new ZipOutputStream(buf)) {
            zos.putNextEntry(new ZipEntry("plugin.json"));
            zos.write(manifestJson.getBytes());
            zos.closeEntry();
        }
        return buf.toByteArray();
    }

    @Test
    void registersPluginFromValidZip() throws Exception {
        byte[] zip = zipWithManifest("""
                {"name":"dingtalk-bot","version":"1.0.0","kind":"WEBHOOK","description":"x"}
                """);
        when(pluginRepository.findByNameAndVersion("dingtalk-bot", "1.0.0")).thenReturn(Optional.empty());
        when(pluginRepository.save(any(Plugin.class))).thenAnswer(inv -> inv.getArgument(0));

        Plugin saved = useCase.execute(new RegisterPluginCommand("dingtalk-bot.zip", zip));

        assertEquals("dingtalk-bot", saved.getName());
        assertEquals("1.0.0", saved.getVersion());
        assertEquals(PluginKind.WEBHOOK, saved.getKind());
        verify(pluginRepository).save(any(Plugin.class));
    }

    @Test
    void rejectsZipWithoutPluginJson() throws Exception {
        ByteArrayOutputStream buf = new ByteArrayOutputStream();
        try (ZipOutputStream zos = new ZipOutputStream(buf)) {
            zos.putNextEntry(new ZipEntry("README.md"));
            zos.write("hi".getBytes());
            zos.closeEntry();
        }
        assertThrows(InvalidPluginPackageException.class,
                () -> useCase.execute(new RegisterPluginCommand("nope.zip", buf.toByteArray())));

        verify(pluginRepository, never()).save(any(Plugin.class));
    }

    @Test
    void rejectsManifestMissingRequiredField() throws Exception {
        byte[] zip = zipWithManifest("""
                {"name":"dingtalk-bot","version":"1.0.0"}
                """);

        assertThrows(InvalidPluginPackageException.class,
                () -> useCase.execute(new RegisterPluginCommand("p.zip", zip)));

        verify(pluginRepository, never()).save(any(Plugin.class));
    }

    @Test
    void rejectsUnknownPluginKind() throws Exception {
        byte[] zip = zipWithManifest("""
                {"name":"x","version":"1.0","kind":"NOT_A_KIND"}
                """);

        assertThrows(InvalidPluginPackageException.class,
                () -> useCase.execute(new RegisterPluginCommand("p.zip", zip)));
    }

    @Test
    void rejectsDuplicatePluginNameAndVersion() throws Exception {
        byte[] zip = zipWithManifest("""
                {"name":"dingtalk-bot","version":"1.0.0","kind":"WEBHOOK"}
                """);
        Plugin existing = Plugin.create("dingtalk-bot", "1.0.0", PluginKind.WEBHOOK, null);
        when(pluginRepository.findByNameAndVersion("dingtalk-bot", "1.0.0")).thenReturn(Optional.of(existing));

        assertThrows(DuplicatePluginException.class,
                () -> useCase.execute(new RegisterPluginCommand("p.zip", zip)));

        verify(pluginRepository, never()).save(any(Plugin.class));
    }
}
